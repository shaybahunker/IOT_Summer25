#include <WiFi.h>
#include <Firebase_ESP_Client.h>

const char* ssid     = "NoasIphone";
const char* password = "06032002";

#define API_KEY       "AIzaSyCp9MhvXE68oYGD4RGYb3NRs2B9z8bk0-M"
#define DATABASE_URL  "https://iot-group9-smart-parking-default-rtdb.firebaseio.com"
#define USER_EMAIL    "iotgroupp9@gmail.com"
#define USER_PASSWORD "Noa55643"

FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

void waitWifi() {
  Serial.print("Wi-Fi: ");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  Serial.print(" connected, IP=");
  Serial.println(WiFi.localIP());
}

void setup() {
  Serial.begin(115200);
  delay(500);

  waitWifi();

  //email/password auth
  config.api_key = API_KEY;
  config.database_url = DATABASE_URL;
  auth.user.email = USER_EMAIL;
  auth.user.password = USER_PASSWORD;

  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  // write a small health record
  bool ok1 = Firebase.RTDB.setString(&fbdo, "/system/health/status", "ok");
  bool ok2 = Firebase.RTDB.setInt(&fbdo, "/system/health/ts_ms", (int)millis());

  Serial.printf("write status: %s\n", (ok1 && ok2) ? "OK" : fbdo.errorReason().c_str());

  //read back
  String back;
  if (Firebase.RTDB.getString(&fbdo, "/system/health/status")) {
    back = fbdo.to<const char*>();
    Serial.print("read status: ");
    Serial.println(back);
  } else {
    Serial.print("read error: ");
    Serial.println(fbdo.errorReason());
  }

  // tiny spot echo
  Firebase.RTDB.setString(&fbdo, "/spots/0/test_note", "hello from esp32");
  Serial.println("done.");
}

void loop() {
  // nothing here
}
