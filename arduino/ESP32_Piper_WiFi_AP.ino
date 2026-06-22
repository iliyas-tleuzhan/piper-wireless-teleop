#include <WiFi.h>
#include "HT_SSD1306Wire.h"

// WiFi AP settings
const char *ssid = "PiperBridgeESP32";
const char *password = "PiperBridge123";

// ESP32 AP network
IPAddress local_IP(192, 168, 4, 1);
IPAddress gateway(192, 168, 4, 1);
IPAddress subnet(255, 255, 255, 0);

// Heltec OLED
SSD1306Wire oled(
  0x3c,
  500000,
  SDA_OLED,
  SCL_OLED,
  GEOMETRY_128_64,
  RST_OLED);

unsigned long lastUpdate = 0;
void showOLED() {
  oled.clear();

  int clients = WiFi.softAPgetStationNum();

  oled.drawString(0, 0, "SSID:");
  oled.drawString(0, 12, String(ssid));

  oled.drawString(0, 26, "PASS:");
  oled.drawString(0, 38, String(password));

  oled.drawString(0, 52, "Clients: " + String(clients));

  oled.display();
}

void printStatus() {
  Serial.println("========== ESP32 Piper WiFi AP ==========");
  Serial.print("SSID: ");
  Serial.println(ssid);

  Serial.print("Password: ");
  Serial.println(password);

  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());

  Serial.print("Connected stations: ");
  Serial.println(WiFi.softAPgetStationNum());

  Serial.println("=========================================");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Power OLED on Heltec boards
  pinMode(Vext, OUTPUT);
  digitalWrite(Vext, LOW);
  delay(100);

  oled.init();
  oled.clear();
  oled.drawString(0, 0, "Starting AP...");
  oled.display();

  Serial.println();
  Serial.println("Starting ESP32 Piper WiFi AP...");

  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);

  bool config_ok = WiFi.softAPConfig(local_IP, gateway, subnet);
  Serial.print("AP config: ");
  Serial.println(config_ok ? "OK" : "FAILED");

  // channel 6, hidden = false, max clients = 4
  bool ap_ok = WiFi.softAP(ssid, password, 6, false, 4);
  Serial.print("AP start: ");
  Serial.println(ap_ok ? "OK" : "FAILED");

  printStatus();
  showOLED();
}

void loop() {
  if (millis() - lastUpdate > 2000) {
    lastUpdate = millis();

    printStatus();
    showOLED();
  }
}