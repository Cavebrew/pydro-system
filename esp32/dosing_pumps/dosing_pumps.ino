/*
 * Dosing Pump Controller ESP32
 * Controls 8 peristaltic pumps (4 per tower)
 * 
 * Cool Tower Pumps (GPIO 12-15):
 *   12 - Epsom Salt
 *   13 - Calcium Nitrate
 *   14 - pH Down
 *   15 - Potassium Bicarbonate
 * 
 * Warm Tower Pumps (GPIO 16-19):
 *   16 - Epsom Salt
 *   17 - Calcium Nitrate
 *   18 - pH Down
 *   19 - Potassium Bicarbonate
 * 
 * MQTT Commands:
 *   /cool/pump/command - JSON: {"pump_id": 1, "run_time_seconds": 10}
 *   /warm/pump/command - JSON: {"pump_id": 5, "run_time_seconds": 10}
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid = "12BravoP";
const char* password = "$apper!2B10";

// MQTT Configuration
const char* mqtt_server = "10.0.0.62";
const int mqtt_port = 1883;
const char* mqtt_user = "hydro_user";
const char* mqtt_password = "your_secure_mqtt_password_here";
const char* mqtt_client_id = "dosing_pump_esp32";

// MQTT Topics
const char* topic_cool_pump_cmd = "/cool/pump/command";
const char* topic_warm_pump_cmd = "/warm/pump/command";
const char* topic_pump_status = "/pumps/status";

// Pump GPIO Pins
const int PUMP_PINS[] = {
    12, 13, 14, 15,  // Cool tower (pumps 1-4)
    16, 17, 18, 19   // Warm tower (pumps 5-8)
};

const int NUM_PUMPS = 8;

// Pump names for logging
const char* PUMP_NAMES[] = {
    "Cool Epsom Salt",
    "Cool Calcium Nitrate",
    "Cool pH Down",
    "Cool K-Bicarbonate",
    "Warm Epsom Salt",
    "Warm Calcium Nitrate",
    "Warm pH Down",
    "Warm K-Bicarbonate"
};

// Safety limits
const unsigned long MAX_RUN_TIME_MS = 60000;  // 60 seconds max
const unsigned long MIN_REST_TIME_MS = 10000;  // 10 seconds between doses

// Pump state tracking
unsigned long lastRunTime[NUM_PUMPS] = {0};
bool isPumpRunning[NUM_PUMPS] = {false};

WiFiClient espClient;
PubSubClient mqtt(espClient);

// Function prototypes
void setupWiFi();
void setupMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void reconnectMQTT();
void runPump(int pumpId, unsigned long durationMs);
void stopAllPumps();
void publishPumpStatus();

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== Dosing Pump Controller Starting ===");
    
    // Setup pump pins
    for (int i = 0; i < NUM_PUMPS; i++) {
        pinMode(PUMP_PINS[i], OUTPUT);
        digitalWrite(PUMP_PINS[i], LOW);  // All pumps off
        Serial.printf("Pump %d (%s) - GPIO %d: READY\n", 
                     i + 1, PUMP_NAMES[i], PUMP_PINS[i]);
    }
    
    // Connect to WiFi and MQTT
    setupWiFi();
    setupMQTT();
    
    Serial.println("=== Dosing Pump Controller Ready ===\n");
}

void loop() {
    // Maintain MQTT connection
    if (!mqtt.connected()) {
        reconnectMQTT();
    }
    mqtt.loop();
    
    // Safety check - stop any pumps running too long
    for (int i = 0; i < NUM_PUMPS; i++) {
        if (isPumpRunning[i]) {
            unsigned long runTime = millis() - lastRunTime[i];
            if (runTime > MAX_RUN_TIME_MS) {
                digitalWrite(PUMP_PINS[i], LOW);
                isPumpRunning[i] = false;
                Serial.printf("SAFETY: Pump %d stopped after %lu ms\n", 
                             i + 1, runTime);
                publishPumpStatus();
            }
        }
    }
    
    delay(100);
}

void setupWiFi() {
    Serial.print("Connecting to WiFi: ");
    Serial.println(ssid);
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi connected!");
        Serial.print("IP address: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\nWiFi connection FAILED!");
    }
}

void setupMQTT() {
    mqtt.setServer(mqtt_server, mqtt_port);
    mqtt.setCallback(mqttCallback);
    reconnectMQTT();
}

void reconnectMQTT() {
    static unsigned long lastAttempt = 0;
    
    if (millis() - lastAttempt < 5000) {
        return;  // Don't try too often
    }
    lastAttempt = millis();
    
    if (!mqtt.connected()) {
        Serial.print("Connecting to MQTT broker... ");
        
        if (mqtt.connect(mqtt_client_id, mqtt_user, mqtt_password)) {
            Serial.println("connected!");
            
            // Subscribe to pump command topics
            mqtt.subscribe(topic_cool_pump_cmd);
            mqtt.subscribe(topic_warm_pump_cmd);
            
            Serial.println("Subscribed to pump command topics");
            publishPumpStatus();
        } else {
            Serial.print("failed, rc=");
            Serial.println(mqtt.state());
        }
    }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    Serial.printf("Message received [%s]: ", topic);
    
    // Parse JSON payload
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, payload, length);
    
    if (error) {
        Serial.println("JSON parse error!");
        return;
    }
    
    // Extract pump command
    int pumpId = doc["pump_id"];
    float runTimeSeconds = doc["run_time_seconds"];
    
    Serial.printf("Pump %d for %.1f seconds\n", pumpId, runTimeSeconds);
    
    // Validate pump ID
    if (pumpId < 1 || pumpId > NUM_PUMPS) {
        Serial.printf("ERROR: Invalid pump ID %d\n", pumpId);
        return;
    }
    
    // Convert to milliseconds
    unsigned long durationMs = (unsigned long)(runTimeSeconds * 1000);
    
    // Safety check
    if (durationMs > MAX_RUN_TIME_MS) {
        Serial.printf("ERROR: Duration %lu ms exceeds max %lu ms\n", 
                     durationMs, MAX_RUN_TIME_MS);
        return;
    }
    
    // Check rest time since last run
    int pumpIndex = pumpId - 1;
    unsigned long timeSinceLastRun = millis() - lastRunTime[pumpIndex];
    
    if (timeSinceLastRun < MIN_REST_TIME_MS && lastRunTime[pumpIndex] > 0) {
        Serial.printf("ERROR: Pump %d needs %lu ms rest (only %lu ms since last run)\n",
                     pumpId, MIN_REST_TIME_MS, timeSinceLastRun);
        return;
    }
    
    // Run the pump
    runPump(pumpId, durationMs);
}

void runPump(int pumpId, unsigned long durationMs) {
    int pumpIndex = pumpId - 1;
    
    Serial.printf("Starting pump %d (%s) for %lu ms\n", 
                 pumpId, PUMP_NAMES[pumpIndex], durationMs);
    
    // Start pump
    digitalWrite(PUMP_PINS[pumpIndex], HIGH);
    isPumpRunning[pumpIndex] = true;
    lastRunTime[pumpIndex] = millis();
    
    publishPumpStatus();
    
    // Wait for duration
    delay(durationMs);
    
    // Stop pump
    digitalWrite(PUMP_PINS[pumpIndex], LOW);
    isPumpRunning[pumpIndex] = false;
    
    Serial.printf("Pump %d stopped\n", pumpId);
    publishPumpStatus();
}

void stopAllPumps() {
    for (int i = 0; i < NUM_PUMPS; i++) {
        digitalWrite(PUMP_PINS[i], LOW);
        isPumpRunning[i] = false;
    }
    Serial.println("All pumps stopped");
    publishPumpStatus();
}

void publishPumpStatus() {
    StaticJsonDocument<512> doc;
    JsonArray pumps = doc.createNestedArray("pumps");
    
    for (int i = 0; i < NUM_PUMPS; i++) {
        JsonObject pump = pumps.createNestedObject();
        pump["id"] = i + 1;
        pump["name"] = PUMP_NAMES[i];
        pump["running"] = isPumpRunning[i];
        pump["gpio"] = PUMP_PINS[i];
        
        if (lastRunTime[i] > 0) {
            pump["last_run_ms_ago"] = millis() - lastRunTime[i];
        }
    }
    
    char buffer[512];
    serializeJson(doc, buffer);
    
    mqtt.publish(topic_pump_status, buffer, true);
}
