#include <Wire.h>
#include <MPU6050.h>
#include <Adafruit_ADS1X15.h>
#include <ESP32Servo.h>

MPU6050 mpu;
Adafruit_ADS1115 ads;
Servo gateServo;

const int servoPin = 6;
const float threshold = 1.3;
const float MAX_VALID_G = 8.0;

const int SDA_PIN = 8;
const int SCL_PIN = 9;

bool gateClosed = false;

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);
  delay(100);

  mpu.initialize();
  mpu.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
  Serial.println("MPU6050 initialized");

  Serial.println("Initializing ADS1115...");
  if (!ads.begin()) {
    Serial.println("ADS1115 initialization failed!");
    while (1) { delay(1000); }
  }
  Serial.println("ADS1115 initialized successfully");
  ads.setGain(GAIN_ONE);

  gateServo.attach(servoPin);
  gateServo.write(0);

  Serial.println("SYSTEM READY");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 'R') {
      gateClosed = false;
    }
  }

  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);

  float axg = ax / 16384.0;
  float ayg = ay / 16384.0;
  float azg = az / 16384.0;
  float magnitude = sqrt((axg * axg) + (ayg * ayg) + (azg * azg));

  bool validReading = (magnitude <= MAX_VALID_G);

  if (validReading && magnitude > threshold) {
    gateClosed = true;
  }

  if (gateClosed) {
    gateServo.write(90);
  } else {
    gateServo.write(0);
  }

  int16_t rawSensor1 = ads.readADC_SingleEnded(0);
  float voltage1 = ads.computeVolts(rawSensor1);
  int16_t rawSensor2 = ads.readADC_SingleEnded(1);
  float voltage2 = ads.computeVolts(rawSensor2);

  if (validReading) {
    Serial.print(magnitude, 4);
    Serial.print(",");
    Serial.print(voltage1, 4);
    Serial.print(",");
    Serial.println(voltage2, 4);
  }

  delay(150);
}