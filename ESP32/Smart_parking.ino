#include <Arduino.h>
#include <ArduinoJson.h>

// ====== CONFIG ======
static const uint8_t PIN_TRIG = 4;
static const uint8_t PIN_ECHO = 5;

// LED output mode: set to true if you have a WS2812B strip with 50 pixels on GPIO 13
#define USE_NEOPIXEL true
#if USE_NEOPIXEL
  #include <Adafruit_NeoPixel.h>
  static const uint8_t PIN_NEOPIXEL = 13;
  static const int NUM_PIXELS = 50;
  Adafruit_NeoPixel strip(NUM_PIXELS, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
#else
  // Fallback: no LEDs, just print intended colors
#endif

// Distance thresholds (centimeters)
static const float OCCUPIED_CM = 20.0f;
static const float MAX_CM = 400.0f;

// ====== DATA MODEL ======
struct Spot {
  float distanceCm;   // NAN means unknown
  bool problem;       // true => orange
  bool reserved;      // true => orange if free
};

Spot spots[50];

// Simple reservation table (plate -> spot index)
struct Reservation { const char* plate; int spot; };
Reservation kReserved[] = {
  {"12-345-67", 7},
  {"AB-123-CD", 21},
  {"99-999-99", 3},
};
const size_t kReservedCount = sizeof(kReserved)/sizeof(kReserved[0]);

int plateToReservedSpot(const String& plate) {
  for (size_t i=0;i<kReservedCount;i++) {
    if (plate.equalsIgnoreCase(kReserved[i].plate)) return kReserved[i].spot;
  }
  return -1;
}

bool isOccupied(const Spot& s) {
  return !isnan(s.distanceCm) && s.distanceCm < OCCUPIED_CM;
}

uint32_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return ((uint32_t)r<<16) | ((uint32_t)g<<8) | b;
}

void setLed(int i, const char* colorName) {
#if USE_NEOPIXEL
  if (i < 0 || i >= strip.numPixels()) return;
  if (strcmp(colorName, "red")==0)       strip.setPixelColor(i, strip.Color(255,0,0));
  else if (strcmp(colorName, "green")==0)strip.setPixelColor(i, strip.Color(0,255,0));
  else if (strcmp(colorName, "orange")==0)strip.setPixelColor(i, strip.Color(255,165,0));
  else                                    strip.setPixelColor(i, strip.Color(0,0,0));
#else
  Serial.printf("[LED %02d] -> %s\n", i, colorName);
#endif
}

void pushLeds() {
#if USE_NEOPIXEL
  strip.show();
#endif
}

// ====== HC-SR04 READ ======
float readHCSR04cm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  unsigned long duration = pulseIn(PIN_ECHO, HIGH, 30000UL); // 30ms timeout ~ 5m
  if (duration == 0) return NAN;
  float cm = duration / 58.0f; // standard scale
  if (cm < 2 || cm > MAX_CM) return NAN;
  return cm;
}

// ====== SETUP ======
void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
#if USE_NEOPIXEL
  strip.begin();
  strip.clear();
  strip.show();
#endif
  for (int i=0;i<50;i++) {
    spots[i].distanceCm = NAN;
    spots[i].problem = false;
    spots[i].reserved = false;
  }
  // Mark reserved flags
  for (size_t i=0;i<kReservedCount;i++) {
    int s = kReserved[i].spot;
    if (s>=0 && s<50) spots[s].reserved = true;
  }
  Serial.println("ESP32 Parking Controller ready.");
  Serial.println("Send JSON lines like:");
  Serial.println(R"({"type":"sensor_update","distances":[null,200,10,...],"problems":[5,18]})");
  Serial.println(R"({"type":"car_enter","plate":"12-345-67"})");
}

// ====== LOGIC ======
int findClosestFreeNonReserved() {
  // simple strategy: lowest index; replace with distance-to-entry if you know layout
  for (int i=0;i<50;i++) {
    if (!spots[i].reserved && !spots[i].problem && !isOccupied(spots[i])) return i;
  }
  return -1;
}

void updateLedsFromState() {
  for (int i=0;i<50;i++) {
    if (spots[i].problem || (spots[i].reserved && !isOccupied(spots[i]))) {
      setLed(i, "orange");
    } else if (isOccupied(spots[i])) {
      setLed(i, "red");
    } else {
      setLed(i, "green");
    }
  }
  pushLeds();
}

void handleCarEnter(const String& plate) {
  int r = plateToReservedSpot(plate);
  if (r >= 0) {
    Serial.printf("[ENTER] Plate %s -> RESERVED spot %d\n", plate.c_str(), r);
    // blink that LED orange a few times
    for (int k=0;k<3;k++){ setLed(r,"orange"); pushLeds(); delay(150); setLed(r,"green"); pushLeds(); delay(150); }
    updateLedsFromState();
    return;
  }
  int s = findClosestFreeNonReserved();
  if (s >= 0) {
    Serial.printf("[ENTER] Plate %s -> NEAREST FREE spot %d\n", plate.c_str(), s);
    for (int k=0;k<3;k++){ setLed(s,"green"); pushLeds(); delay(150); setLed(s,"red"); pushLeds(); delay(150); }
    updateLedsFromState();
  } else {
    Serial.printf("[ENTER] Plate %s -> NO FREE SPOT AVAILABLE\n", plate.c_str());
  }
}

String inbuf;

void processJsonLine(const String& line) {
  StaticJsonDocument<8192> doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) { Serial.printf("JSON parse error: %s\n", err.c_str()); return; }

  const char* type = doc["type"] | "";
  if (strcmp(type, "sensor_update")==0) {
    // distances: index 0 should be null because spot 0 is real sensor
    JsonArray arr = doc["distances"].as<JsonArray>();
    if (!arr.isNull()) {
      for (int i=1;i<50 && i<(int)arr.size();i++) {
        if (arr[i].isNull()) { spots[i].distanceCm = NAN; }
        else { spots[i].distanceCm = arr[i].as<float>(); }
      }
    }
    // problems: array of spot indices
    for (int i=0;i<50;i++) spots[i].problem = false;
    if (doc["problems"].is<JsonArray>()) {
      for (int idx : doc["problems"].as<JsonArray>()) {
        if (idx>=0 && idx<50) spots[idx].problem = true;
      }
    }
    updateLedsFromState();
  } else if (strcmp(type, "car_enter")==0) {
    String plate = doc["plate"].as<String>();
    handleCarEnter(plate);
  } else {
    Serial.println("Unknown message type.");
  }
}

unsigned long lastSensor0Ms = 0;

void loop() {
  // 1) Read real sensor for spot 0 every 150 ms
  unsigned long now = millis();
  if (now - lastSensor0Ms > 150) {
    lastSensor0Ms = now;
    float cm = readHCSR04cm();
    spots[0].distanceCm = cm;
    // Keep LEDs fresh
    updateLedsFromState();
  }

  // 2) Read lines from Serial (simulation and car entries)
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c=='\n' || c=='\r') {
      if (inbuf.length()) { processJsonLine(inbuf); inbuf = ""; }
    } else {
      inbuf += c;
      if (inbuf.length() > 7000) inbuf = ""; // safety flush
    }
  }
}
