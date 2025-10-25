//hardware test for sensor
const int trigPin =5;
const int echoPin = 18;
#define SOUND_SPEED 0.034f
float distance = 0;

void setup() {
  Serial.begin(115200);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  Serial.println("Starting sensor test...");
}

void loop() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) {
    Serial.println("No echo");
  } else {
    distance = duration * SOUND_SPEED / 2;
    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.println(" cm");

    if (distance < 100) Serial.println("→ Spot TAKEN");
    else Serial.println("→ Spot FREE");
  }
  delay(1000);
}
