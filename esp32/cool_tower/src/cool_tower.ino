/*
 * Cool Tower ESP32-S3 Sensor Controller
 * Monitors EC, pH, water temp, and shared DHT22 air temp/humidity
 * Controls LED grow lights via MOSFET
 * Publishes to MQTT broker on RPi5
 * 
 * Sensors:
 * - Atlas EC Mini (I2C address 0x64)
 * - Gen 3 pH (I2C address 0x63)
 * - DS18B20 (OneWire on pin 4)
 * - DHT22 (pin 15 - publishes to shared environment topic)
 * 
 * Actuators:
 * - MOSFET LED control (PWM on pin 25)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <ArduinoOTA.h>

// WiFi credentials
const char* ssid = "12BravoP";
const char* password = "$apper!2B10";

// MQTT Configuration
const char* mqtt_server = "10.0.0.62";
const int mqtt_port = 1883;
const char* mqtt_user = "hydro_user";
const char* mqtt_password = "your_secure_mqtt_password_here";
const char* mqtt_client_id = "cool_tower_esp32";

// MQTT Topics (short format)
const char* topic_ec = "/cool/ec";
const char* topic_ph = "/cool/ph";
const char* topic_water_temp = "/cool/water_temp";
const char* topic_air_temp = "/cool/air_temp";
const char* topic_humidity = "/cool/air_humidity";
const char* topic_led = "/cool/led";
const char* topic_led_intensity = "/cool/led/intensity";
const char* topic_pump = "/cool/pump/command";
const char* topic_status = "/cool/status";

// Pin Definitions
#define I2C_SDA 41
#define I2C_SCL 42
#define ONE_WIRE_BUS 5       // DS18B20 water temp sensor
#define LED_PWM_PIN 6        // MOSFET control for LED lights
#define DHT_PIN 9            // DHT22 air temp/humidity
#define HC_SR04_TRIG 7       // Ultrasonic sensor trigger
#define HC_SR04_ECHO 8       // Ultrasonic sensor echo
#define DHT_TYPE DHT22
#define LED_PWM_CHANNEL 0
#define LED_PWM_FREQ 5000
#define LED_PWM_RESOLUTION 8  // 8-bit (0-255)

// Atlas EZO I2C Addresses
#define ATLAS_EC_ADDR 0x64
#define ATLAS_PH_ADDR 0x63

// Timing
unsigned long lastSensorRead = 0;
const unsigned long sensorInterval = 60000;  // Read sensors every 60 seconds
unsigned long lastMqttReconnect = 0;
const unsigned long mqttReconnectInterval = 5000;

// Sensor objects
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature waterTempSensor(&oneWire);
DHT dht(DHT_PIN, DHT_TYPE);

WiFiClient espClient;
PubSubClient mqtt(espClient);

// LED intensity (0-100%)
int ledIntensity = 75;  // Default 75%

// Function prototypes
void setupWiFi();
void setupMQTT();
void setupOTA();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void reconnectMQTT();
float readAtlasEC();
float readAtlasPH();
float readWaterTemp();
void readDHT22();
void setLEDIntensity(int intensity);
void publishSensorData();
String atlasCommand(uint8_t address, const char* command, int delayMs = 600);

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=== Cool Tower ESP32-S3 Starting ===");
  
  // Initialize I2C
  Wire.begin();
  
  // Initialize sensors
  waterTempSensor.begin();
  dht.begin();
  
  // Initialize LED PWM
  ledcSetup(LED_PWM_CHANNEL, LED_PWM_FREQ, LED_PWM_RESOLUTION);
  ledcAttachPin(LED_PWM_PIN, LED_PWM_CHANNEL);
  setLEDIntensity(ledIntensity);
  
  // Connect to WiFi
  setupWiFi();
  
  // Setup MQTT
  setupMQTT();
  
  // Setup OTA
  setupOTA();
  
  Serial.println("=== Setup Complete ===\n");
}

void loop() {
  // Handle OTA updates
  ArduinoOTA.handle();
  
  // Maintain MQTT connection
  if (!mqtt.connected()) {
    if (millis() - lastMqttReconnect > mqttReconnectInterval) {
      lastMqttReconnect = millis();
      reconnectMQTT();
    }
  } else {
    mqtt.loop();
  }
  
  // Read and publish sensor data
  if (millis() - lastSensorRead > sensorInterval) {
    lastSensorRead = millis();
    publishSensorData();
  }
}

void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi connection failed!");
  }
}

void setupMQTT() {
  mqtt.setServer(mqtt_server, mqtt_port);
  mqtt.setCallback(mqttCallback);
  reconnectMQTT();
}

void setupOTA() {
  ArduinoOTA.setHostname("cool_tower_esp32");
  ArduinoOTA.setPassword("pydro_ota_password");  // Change this to a secure password
  
  ArduinoOTA.onStart([]() {
    String type = (ArduinoOTA.getCommand() == U_FLASH) ? "sketch" : "filesystem";
    Serial.println("OTA Start updating " + type);
    mqtt.disconnect();  // Disconnect MQTT during update
  });
  
  ArduinoOTA.onEnd([]() {
    Serial.println("\nOTA End");
  });
  
  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("OTA Progress: %u%%\r", (progress / (total / 100)));
  });
  
  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("OTA Error[%u]: ", error);
    if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
    else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
    else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
    else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
    else if (error == OTA_END_ERROR) Serial.println("End Failed");
  });
  
  ArduinoOTA.begin();
  Serial.println("OTA Ready");
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message received [");
  Serial.print(topic);
  Serial.print("]: ");
  
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);
  
  // Handle LED intensity commands
  if (strcmp(topic, topic_led_intensity) == 0) {
    int intensity = message.toInt();
    if (intensity >= 0 && intensity <= 100) {
      setLEDIntensity(intensity);
      Serial.print("LED intensity set to: ");
      Serial.print(intensity);
      Serial.println("%");
    }
  }
}

void reconnectMQTT() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  Serial.print("Attempting MQTT connection...");
  
  if (mqtt.connect(mqtt_client_id, mqtt_user, mqtt_password)) {
    Serial.println("connected!");
    
    // Subscribe to command topics
    mqtt.subscribe(topic_led_intensity);
    
    // Publish status
    StaticJsonDocument<200> statusDoc;
    statusDoc["status"] = "online";
    statusDoc["tower"] = "cool";
    statusDoc["ip"] = WiFi.localIP().toString();
    statusDoc["led_intensity"] = ledIntensity;
    
    char statusBuffer[200];
    serializeJson(statusDoc, statusBuffer);
    mqtt.publish(topic_status, statusBuffer, true);
    
  } else {
    Serial.print("failed, rc=");
    Serial.println(mqtt.state());
  }
}

void publishSensorData() {
  Serial.println("\n--- Reading Sensors ---");
  
  // Read sensors
  float ec = readAtlasEC();
  float ph = readAtlasPH();
  float waterTemp = readWaterTemp();
  
  // Publish individual readings
  if (ec >= 0) {
    char ecStr[10];
    dtostrf(ec, 4, 2, ecStr);
    mqtt.publish(topic_ec, ecStr);
    Serial.print("EC: ");
    Serial.print(ecStr);
    Serial.println(" mS/cm");
  }
  
  if (ph >= 0) {
    char phStr[10];
    dtostrf(ph, 4, 2, phStr);
    mqtt.publish(topic_ph, phStr);
    Serial.print("pH: ");
    Serial.println(phStr);
  }
  
  if (waterTemp > -100) {  // Valid reading
    char tempStr[10];
    dtostrf(waterTemp, 4, 1, tempStr);
    mqtt.publish(topic_water_temp, tempStr);
    Serial.print("Water Temp: ");
    Serial.print(tempStr);
    Serial.println("°F");
  }
  
  // Read DHT22 (shared environment sensor)
  readDHT22();
  
  Serial.println("--- Sensors Complete ---\n");
}

float readAtlasEC() {
  String response = atlasCommand(ATLAS_EC_ADDR, "R", 600);
  if (response.length() > 0 && response.charAt(0) != 'E') {
    return response.toFloat();
  }
  return -1.0;
}

float readAtlasPH() {
  String response = atlasCommand(ATLAS_PH_ADDR, "R", 900);
  if (response.length() > 0 && response.charAt(0) != 'E') {
    return response.toFloat();
  }
  return -1.0;
}

String atlasCommand(uint8_t address, const char* command, int delayMs) {
  Wire.beginTransmission(address);
  Wire.write(command);
  Wire.endTransmission();
  
  delay(delayMs);
  
  Wire.requestFrom(address, 32, 1);
  byte code = Wire.read();
  
  String response = "";
  while (Wire.available()) {
    char c = Wire.read();
    if (c != 0) {
      response += c;
    }
  }
  
  if (code == 1) {  // Success
    return response;
  }
  return "";
}

float readWaterTemp() {
  waterTempSensor.requestTemperatures();
  float tempC = waterTempSensor.getTempCByIndex(0);
  
  if (tempC != DEVICE_DISCONNECTED_C) {
    float tempF = tempC * 9.0 / 5.0 + 32.0;
    return tempF;
  }
  return -999.0;
}

void readDHT22() {
  float humidity = dht.readHumidity();
  float tempF = dht.readTemperature(true);  // True for Fahrenheit
  
  if (!isnan(humidity) && !isnan(tempF)) {
    char humStr[10], tempStr[10];
    dtostrf(humidity, 4, 1, humStr);
    dtostrf(tempF, 4, 1, tempStr);
    
    mqtt.publish(topic_air_temp, tempStr);
    mqtt.publish(topic_humidity, humStr);
    
    Serial.print("Air Temp: ");
    Serial.print(tempStr);
    Serial.print("°F, Humidity: ");
    Serial.print(humStr);
    Serial.println("%");
  } else {
    Serial.println("DHT22 read failed!");
  }
}

void setLEDIntensity(int intensity) {
  ledIntensity = constrain(intensity, 0, 100);
  int pwmValue = map(ledIntensity, 0, 100, 0, 255);
  ledcWrite(LED_PWM_CHANNEL, pwmValue);
}
