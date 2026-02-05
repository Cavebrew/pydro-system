# Machine Learning Models for Plant Deficiency Detection

This directory contains TensorFlow Lite models for detecting plant health issues, deficiencies, and harvest readiness.

## Required Model

**File**: `plant_deficiency_model.tflite`

This model should classify plant images into the following categories:

### Model Classes

| Class ID | Class Name | Description |
|----------|------------|-------------|
| 0 | healthy | Healthy plant with no visible issues |
| 1 | nitrogen_deficiency | Yellowing leaves (chlorosis) |
| 2 | calcium_deficiency | Tip burn, brown leaf edges |
| 3 | phosphorus_deficiency | Purple veins, dark leaves |
| 4 | magnesium_deficiency | Interveinal chlorosis |
| 5 | potassium_deficiency | Brown spots on leaf edges |
| 6 | ready_for_harvest | Mature plant ready to harvest |
| 7 | bolting_flowering | Plant beginning to flower/bolt |

## Model Requirements

### Input
- **Shape**: `[1, 224, 224, 3]` (or model-specific dimensions)
- **Type**: Float32
- **Range**: 0.0 - 1.0 (normalized pixel values)
- **Color Space**: RGB

### Output
- **Shape**: `[1, 8]` (8 classes)
- **Type**: Float32
- **Format**: Softmax probabilities

## Creating Your Own Model

### Option 1: Use Pre-trained PlantVillage Dataset

```python
# Example using TensorFlow
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.models import Model

# Load base model
base_model = MobileNetV2(weights='imagenet', include_top=False, 
                         input_shape=(224, 224, 3))

# Add classification head
x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dense(128, activation='relu')(x)
predictions = Dense(8, activation='softmax')(x)

model = Model(inputs=base_model.input, outputs=predictions)

# Compile
model.compile(optimizer='adam',
              loss='categorical_crossentropy',
              metrics=['accuracy'])

# Train on your dataset
# model.fit(train_data, epochs=50, validation_data=val_data)

# Convert to TFLite
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

with open('plant_deficiency_model.tflite', 'wb') as f:
    f.write(tflite_model)
```

### Option 2: Fine-tune for Hydroponics

Collect your own dataset:
1. Capture images of your plants in various stages
2. Label deficiencies manually
3. Use data augmentation (rotation, brightness, etc.)
4. Fine-tune pre-trained model
5. Target >95% accuracy for production use

### Dataset Structure

```
dataset/
├── train/
│   ├── healthy/
│   ├── nitrogen_deficiency/
│   ├── calcium_deficiency/
│   └── ...
├── val/
│   ├── healthy/
│   └── ...
└── test/
    ├── healthy/
    └── ...
```

### Training Tips

1. **Balance dataset**: Equal samples per class
2. **Augmentation**: Flip, rotate, brightness/contrast variations
3. **Lighting conditions**: Train on images from different times of day
4. **Background**: Include tower/system background in training
5. **Resolution**: Match camera resolution (2304x1296 → resize to 224x224)

## Using Pre-trained Models

### PlantVillage Models
- Source: https://github.com/spMohanty/PlantVillage-Dataset
- Covers many plant diseases (tomato, potato, etc.)
- Adapt for lettuce, basil, oregano, dill

### Transfer Learning
1. Download ImageNet-pretrained MobileNetV2/EfficientNet
2. Remove top classification layer
3. Add custom head for 8 classes
4. Fine-tune on hydroponic plant images

## Model Optimization

### For Raspberry Pi AI Hat 2

```python
# Quantize for faster inference
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.uint8
converter.inference_output_type = tf.uint8

# Representative dataset for quantization
def representative_data_gen():
    for _ in range(100):
        yield [np.random.uniform(0, 255, (1, 224, 224, 3)).astype(np.uint8)]

converter.representative_dataset = representative_data_gen
tflite_model = converter.convert()
```

## Testing Model Performance

```python
import numpy as np
import tflite_runtime.interpreter as tflite
import cv2

# Load model
interpreter = tflite.Interpreter(model_path='plant_deficiency_model.tflite')
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# Load test image
img = cv2.imread('test_lettuce.jpg')
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
img = cv2.resize(img, (224, 224))
img = img.astype(np.float32) / 255.0
img = np.expand_dims(img, axis=0)

# Inference
interpreter.set_tensor(input_details[0]['index'], img)
interpreter.invoke()
output = interpreter.get_tensor(output_details[0]['index'])

# Results
classes = ['healthy', 'nitrogen_deficiency', 'calcium_deficiency', 
           'phosphorus_deficiency', 'magnesium_deficiency', 
           'potassium_deficiency', 'ready_for_harvest', 'bolting_flowering']

predictions = output[0]
top_class = classes[np.argmax(predictions)]
confidence = np.max(predictions)

print(f"Prediction: {top_class} ({confidence*100:.1f}% confidence)")
```

## Model Versioning

- Name models with version/date: `plant_deficiency_v1.0_20260204.tflite`
- Keep changelog of improvements
- A/B test new models before production deployment
- Track accuracy metrics in production

## Fallback Strategy

If no model is available, the system uses **rule-based color analysis**:
- Yellow detection → Nitrogen deficiency
- Brown edges → Calcium deficiency (tip burn)
- Purple hues → Phosphorus deficiency

See `rpi5/image_analyzer.py` for implementation.

## Performance Targets

- **Inference Time**: <500ms per image (on RPi5 with AI Hat 2)
- **Accuracy**: >95% on validation set
- **False Positive Rate**: <5%
- **Model Size**: <10MB (for TFLite)

## Resources

- [PlantVillage Dataset](https://github.com/spMohanty/PlantVillage-Dataset)
- [TensorFlow Lite Guide](https://www.tensorflow.org/lite/guide)
- [Raspberry Pi AI HAT+ Examples](https://github.com/raspberrypi/ai-hat-examples)
- [Transfer Learning Tutorial](https://www.tensorflow.org/tutorials/images/transfer_learning)

---

**Note**: Until you have a trained model, the system will use color-based analysis as a fallback. This works reasonably well for common deficiencies but lacks the precision of ML-based detection.
