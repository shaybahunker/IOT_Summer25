// group 9 project in Arduino for smart parking. in this project, there are 50 parking sports wehre spot 0 is the real sesnor and 1-49 are simulated. the parking is
// in the layout you can see in the python ui or in the poster. it holds 2 floors, floor 1: spots 1-25, floor 2: spots 26-50. spot 0 is the real sensor used to example the
// working sensor. the distance from the entry point is determind by manhaten distance by the coordinates of the spots and then they are stored in a min heap data base to
// keep track on the closest free spot.

#include <WiFi.h>
#include <Firebase_ESP_Client.h>
#include <vector>
#include <queue>
#include <deque>
#include <functional>

//wifi configurations
const char* ssid = "NoasIphone";
const char* password = "06032002";

//Firebase configurations 
#define API_KEY       "AIzaSyCp9MhvXE68oYGD4RGYb3NRs2B9z8bk0-M"
#define DATABASE_URL  "https://iot-group9-smart-parking-default-rtdb.firebaseio.com"
#define USER_EMAIL    "iotgroupp9@gmail.com" //a user to have authintication so no other side can write fake data to our FB 
#define USER_PASSWORD "Noa55643"

FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

//configurations for spot 0, the real sensor
const int sensor_send_info =5; //how often the sensor sends info
const int sensor_recive =18;//how often the sensor recives info
#define SOUND_SPEED 0.034f
const float OCCUPIED_ON_CM  =100.0; //if distance is less, taken
const float OCCUPIED_OFF_CM = 101.0; //if distance is more, taken
const int   SAMPLES_FOR_AVG= 5;//how many SAMPLES_FOR_AVG to take avg of distance
const int TOTAL_SPOTS = 50; //total parking spots
const unsigned long ARRIVAL_INTERVAL_MS = 3000; //how often car arrives to parking lot
const unsigned long SENSOR_PUSH_MS= 20000;//how often sesor pushes info
const unsigned long STAY_MIN_MS= 60000; //min time for car to stay parked
const unsigned long STAY_MAX_MS= 60000;//min time for car to stay parked(means car stays 1min)
const float CELL_CM= 100.0f; //distance between parking spot
const float FLOOR_PENALTY_CM =2000.0f;//distance to floor 2

//remember last valid spot-0
float lastSpot0Cm = 0.0f;     // last valid distance for spot 0
bool  hasLastSpot0 = false;    //valid reading exists?

//coordinations for the spots (x,y,floor)
struct XY { uint8_t x;uint8_t y; uint8_t floor; };
XY spotXY[TOTAL_SPOTS] = {{0,1,1},{1, 1,1},{2,1,1},{3,1,1},{4,1,1},{5,1,1}, {1,2,1},{2,2,1}, {3,2,1},{4,2,1},{5 ,2,1},
  {1,3,1},{2 ,3,1},{3,3,1},{4,3,1},{5 ,3,1},
  {1,4,1},{2,4,1},{3,4,1},{4,4, 1},{5 ,4,1},
  {1,5,1},{2,5 ,1},{3, 5,1},{4,5 ,1},{5,5,1},
  {1,1,2},{2,1,2},{3,1, 2},{4,1,2},{5,1,2},
  {1,2,2},{2, 2,2},{3,2, 2},{4,2,2},{5,2,2},
  {1,3,2 },{2,3,2},{3,3,2},{4,3,2},{5,3,2},
  {1, 4, 2},{2,4,2},{ 3, 4, 2},{4,4,2},{5,4,2},
  {1 ,5, 2},{2,5,2},{3,5,2},{4,5,2}};

enum SpotState { FREE=0,
TAKEN=1, 
RESERVED=2 }; //enum to send spot state to firebase
SpotState spotState[TOTAL_SPOTS];//array of all spots, each described as a state because it can only be one of 3, free taken or reserved
float spotLayoutDistCm[TOTAL_SPOTS];
String plate_of_the_spot[TOTAL_SPOTS];
String spot_is_reserved_for[TOTAL_SPOTS];
unsigned long carWillLeaveSpot[TOTAL_SPOTS]; //when car will leave spot

using HeapKey= std::pair<float,int>;
struct CompareMinOprt //this is a comperison to use for min heap, to determine which spot is closer.
{
  bool operator()(const HeapKey& spot1, const HeapKey& spot2) const{
    if (spot1.first != spot2.first) return spot1.first> spot2.first; 
    return spot1.second > spot2.second;
  }
};
std::priority_queue<HeapKey,std::vector<HeapKey>,CompareMinOprt> minHeapForFreeSpots; //the min heap

String spotLabel(int id) //this names the spots, for example "P01"
{ 
  char b[6]; 
  snprintf(b,sizeof(b),"P%02d",id); 
  return String(b); 
}

// these functions send data to fire base
void markLotState(const char* stat){ 
  Firebase.RTDB.setString(&fbdo, "/system/lot_state", stat); } //state of the lot if there is still space

void logRejectedArrival(const String& plate, const char* reasonreject){ //was car rejected? (queue full)
  FirebaseJson jas; 
  jas.set("plate", plate); 
  jas.set("ts", millis()); 
  jas.set("reason", reasonreject);
  Firebase.RTDB.pushJSON(&fbdo, "/system/rejected_arrivals", &jas);
}

void logEnqueued(const String& plate){ //car enters queue, its logged
  FirebaseJson jason; jason.set("plate", plate); 
  jason.set("ts", millis());
  jason.set("event", "ENQUEUED");
  Firebase.RTDB.pushJSON(&fbdo, "/system/queue_events", &jason);
}
void logDequeuedAssign(const String& plate, int spotId){ //gets a parking spot
  FirebaseJson jason; 
  jason.set("plate", plate); 
  jason.set("ts", millis()); jason.set("event", "DEQUEUED_TO_SPOT"); 
  jason.set("spot", spotId);
  Firebase.RTDB.pushJSON(&fbdo, "/system/queue_events", &jason);
}
void logTimeout(const String& plate){ //to long in queue, removed
  FirebaseJson jason; 
  jason.set("plate", plate); 
  jason.set("ts", millis()); 
  jason.set("event", "QUEUE_TIMEOUT");
  Firebase.RTDB.pushJSON(&fbdo, "/system/queue_events", &jason);
}
//this generets random israeli plate to send to spots to do simulation, we later check no plate apear twice
String genIsraeliPlate(){
  int r=random(0,10); 
  char buf[16];
  if(r<7)
  {
    int a=random(100,1000),b =random(10,100),c= random(100,1000);
    snprintf(buf, sizeof(buf),"%03d-%02d-%03d",a,b,c);
  }
  else
  {
    int a=random(10,100),b=random(100,1000),c=random(10,100);
    snprintf(buf,sizeof(buf),"%02d-%03d-%02d", a,b,c);
    }
  return String(buf);
}
String normalizePlate(const String& p){
  String the_plate;
  for(size_t i=0;i<p.length();++i){
    char c = p[i];
    if(c!='-' && c!=' '){the_plate += (char)toupper((unsigned char)c); }
  }
  return the_plate;
}

// using manhattan distace to calculate the distances to the entrance. note that the distance of each spot from the entrance is contant, because spots cordinations don't change.
// we choe to use this calculation because the parkings are presented by (x,y,floor), which is a perferct data fot manhatten calculation.
float computeManhattanCm(int id){ //gets id of ptking spot, return x,y,f of it
  XY c= spotXY[id];
  float calc=(c.x+c.y)*CELL_CM;
  if(c.floor==2) calc+=FLOOR_PENALTY_CM; //second floor is more far, we preffer first floor
  return calc;}

//this is only for spot zero, which is as mentioned the spot that reads from the real sensor. to get accurate data, we sample few samples and avg them to get better result
float readDistanceCmAveraged(){
  float sum_of_dist=0;
  int amount=0;
  for(int i=0;i<SAMPLES_FOR_AVG;i++){ //sample up to the const SAMPLES_FOR_AVG
    digitalWrite(sensor_send_info,LOW); delayMicroseconds(2);
    digitalWrite(sensor_send_info,HIGH); delayMicroseconds(10);
    digitalWrite(sensor_send_info,LOW);
    long dur= pulseIn(sensor_recive,HIGH,30000);
    if(dur> 0)
    {float d=dur*SOUND_SPEED/2.0f; if(d>0&&d<=400.0f){sum_of_dist+=d;
    amount++;}}
    delay(10);
  }
  if(amount==0) return -1.0f;
  return sum_of_dist/amount;
}

SpotState stateFromDistanceReading(float distance_cm){ //determine the state of the spots, by the cosnt defined above. if it is reserved, it will ignore this
  if(distance_cm<=0) return FREE;
  if(distance_cm<=OCCUPIED_ON_CM){
    return TAKEN;
  } 
  if(distance_cm>=OCCUPIED_OFF_CM){
    return FREE;
  }
  return FREE; //edge case, just in case
}

//heap funcs to manage all free spots
void heapPushIfFree(int id_spot){
  if(id_spot<=0) return; //spots 1-49
  if(spotState[id_spot]==FREE) minHeapForFreeSpots.push({spotLayoutDistCm[id_spot],id_spot});
}
int heapPopClosestFree(){
  while( !minHeapForFreeSpots.empty()) {
    HeapKey spot_k =minHeapForFreeSpots.top(); 
    int id= spot_k.second;
    if(spotState[id] ==FREE){ //spot might be taken but not taken out of the heap yet
      minHeapForFreeSpots.pop(); 
      return id;}
    minHeapForFreeSpots.pop();
  }
  return -1;
}

//gamification element, we inc points for every time a car parks in the spot assign to it. later can be seen in the ui all points of cars
bool incrementPointsForPlate(const String& car_plat){
  String plate = normalizePlate(car_plat);
  FirebaseJson jason;
  jason.set("points/.sv/increment",1);
  String path = "/drivers_by_plate/" +plate;
  bool ok =Firebase.RTDB.updateNode(&fbdo, path.c_str(),&jason);
  if( !ok){
    Serial.printf("Increment FAILED for %s : %s\n", plate.c_str(), fbdo.errorReason().c_str());
  }
  else{Serial.printf("Incremented points for %s\n", plate.c_str());}
  return ok;
}

//fifo for queue of cars waing in it
struct Wait {String plate; unsigned long expire;};
std::deque<Wait> waitQ;
const int MAX_Q =5; // max num of cars in the queue
const unsigned long MAX_WAIT_MS =180000; // 3 minutes to wait max in queue

bool isPlateAlreadyParked(const String& plate){ //becase plates are random, we dont want the same plate to park twice because a plate is uniqe
  for(int i=1;i< TOTAL_SPOTS;i++){ //going over all parked cars
    if(spotState[i]==TAKEN && plate_of_the_spot[i]==plate){
      return true;
    } 
  }
  return false;
}
void purgeQueueTimeouts(){
  while(!waitQ.empty()){
    long dt = (long)(millis() -waitQ.front().expire);
    if(dt > 0){
      logTimeout(waitQ.front().plate);
      waitQ.pop_front();
    }else break;
  }
}

void updateLotState(){
  for(int i=1 ;i< TOTAL_SPOTS;i++){
    if(spotState[i] ==FREE){ 
      markLotState("HAS_FREE"); return; } //the lot has a free spot, we use this to notify the queue
  }
  if( !waitQ.empty())
  { 
    markLotState("QUEUEING"); } //still cars in queue
  else{ markLotState("FULL"); 
  }
}

//check if spot actually avaliable
bool commitIfAssignable(int id, const String& plate, unsigned long now, bool allowReserved){
  if(id <1) return false; //dont use spot 0
  bool okState = (spotState[id]==FREE) || (allowReserved && spotState[id]== RESERVED);
  if(!okState) return false;
  // commit to ram
  spotState[id]=TAKEN;
  plate_of_the_spot[id]=plate;
  carWillLeaveSpot[id]= now +random(STAY_MIN_MS,STAY_MAX_MS+1);
  spot_is_reserved_for[id]= "";
  String base_of_string_for_plate="/spots/"+String(id);
  if(!Firebase.RTDB.setString(&fbdo, base_of_string_for_plate+"/state","TAKEN")){
    spotState[id]=FREE; plate_of_the_spot[id]=""; carWillLeaveSpot[id]=0; // rollback
    heapPushIfFree(id); //check if need to push back to heap
    return false;
  }
  Firebase.RTDB.setString(&fbdo, base_of_string_for_plate+"/plate", plate);
  Firebase.RTDB.setString(&fbdo, base_of_string_for_plate+"/reserved_for", "");
  Firebase.RTDB.setFloat(&fbdo, base_of_string_for_plate+"/layout_distance_cm",spotLayoutDistCm[id]);
  return true;
}

//simulation part, here we control everything that happends in the simultion
unsigned long lastArrivalMs_tracker=0,lastSensorMs_track= 0 ;
int arrivalCount=0 ;
std::vector<int> reservedindices;
std::vector<String> reservedPlates;
std::vector<String> knownPlates; //again, so no plate will repeat itself

String pickPlateForNormalArrival(){ //cars that are not reserved called normal
  if(!knownPlates.empty()&& random(0,100) <70){
    int idx =random(0,(int)knownPlates.size()) ;
    return knownPlates[idx];
  }
  String p =genIsraeliPlate();
  knownPlates.push_back(p);
  return p;
}
void setup(){
  Serial.begin(115200); //num for serial monitor
  pinMode(sensor_send_info,OUTPUT);
  pinMode(sensor_recive,INPUT);
  Serial.printf("Connecting to %s ",ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid,password);
  while(WiFi.status()!=WL_CONNECTED) {delay(500);Serial.print(".");}
  Serial.println(" CONNECTED");
  //firebase configurations
  config.api_key=API_KEY;
  config.database_url=DATABASE_URL;
  auth.user.email=USER_EMAIL;
  auth.user.password=USER_PASSWORD;
  Firebase.begin(&config,&auth);
  Firebase.reconnectWiFi(true);
  randomSeed((uint32_t)esp_random());
  for(int i=0;i<TOTAL_SPOTS ; i++){ //layout for spots
    spotLayoutDistCm[i]= computeManhattanCm(i);
    spotState[i]=FREE; //setting all spots free
    plate_of_the_spot[i]="";
    spot_is_reserved_for[i]="";
    carWillLeaveSpot[i]=0;
  }

  //repeat visitors, good for empphasizing gamification
  for(int i=0;i<30;i++){ knownPlates.push_back(genIsraeliPlate());}

  delay(60000); //delay to start simulation on time

  //we choose 20 random plates to mark them as reserved
  while(reservedindices.size()<20){ //keep going until 20 spots are found
    int random_spot=random(1,TOTAL_SPOTS);
    bool used=false;
    for(int id:reservedindices) if(id==random_spot) {used=true; 
    break; }
    if(!used) reservedindices.push_back(random_spot);
  }
  for(int id:reservedindices){//save spot for plate ***
    String plate=genIsraeliPlate();
    reservedPlates.push_back(plate);
    spotState[id]=RESERVED;
    spot_is_reserved_for[id]=plate;
    String base="/spots/"+String(id);
    Firebase.RTDB.setString(&fbdo,base+"/state","RESERVED");
    Firebase.RTDB.setString(&fbdo,base+"/reserved_for",plate);
    Firebase.RTDB.setString(&fbdo,base+"/plate","");
    Firebase.RTDB.setFloat(&fbdo,base+"/layout_distance_cm",spotLayoutDistCm[id]);
    Serial.println("Reserved spot "+spotLabel(id)+" for plate "+plate);
  }
  for(int i=1;i< TOTAL_SPOTS;i++) if(spotState[i]==FREE) minHeapForFreeSpots.push({spotLayoutDistCm[i],i}); //if not picked for reserved, free
  updateLotState();
  Serial.println("Ready. 20 random reserved spots created.");
}

void loop(){
  unsigned long now=millis();

  //sensor 0 data report
  if(now-lastSensorMs_track>= SENSOR_PUSH_MS|| lastSensorMs_track ==0){
    lastSensorMs_track=now;
    float d0=readDistanceCmAveraged();

    // if invalid, reuse previous valid; if none yet, skip writing this tick
    if (d0 < 0) {
      if (hasLastSpot0) {
        d0 = lastSpot0Cm;
      } else {
        Serial.println("Spot (0) -> no valid reading yet, keeping previous state");
        // skip firebase writes when there is no valid history yet
        goto SKIP_SPOT0_PUSH;
      }
    } else {
      lastSpot0Cm = d0;
      hasLastSpot0 = true;
    }

    spotState[0]=stateFromDistanceReading(d0);
    Firebase.RTDB.setFloat(&fbdo,"/spots/0/distance_cm",d0);
    Firebase.RTDB.setString(&fbdo,"/spots/0/state",spotState[0]==TAKEN?"TAKEN":"FREE");
    Firebase.RTDB.setFloat(&fbdo,"/spots/0/layout_distance_cm",spotLayoutDistCm[0]);
    Serial.printf("Spot (0) -> %s (%.1f cm)\n",spotState[0]==TAKEN?"TAKEN":"FREE",d0);

SKIP_SPOT0_PUSH: ;
  }

  //cars departures
  for(int i=1;i<TOTAL_SPOTS;i++){
    if(spotState[i]==TAKEN&& carWillLeaveSpot[i]>0 && now>=carWillLeaveSpot[i]){
      String plate=plate_of_the_spot[i];
      if(plate.length()>0){ incrementPointsForPlate(plate); }//gamification
      spotState[i]=FREE;
      carWillLeaveSpot[i]=0;
      plate_of_the_spot[i]="";
      spot_is_reserved_for[i]="";
      heapPushIfFree(i);
      String base="/spots/"+String(i);
      Firebase.RTDB.setString(&fbdo, base+"/state","FREE");
      Firebase.RTDB.setString(&fbdo,base+"/plate","");
      Firebase.RTDB.setString(&fbdo, base+"/reserved_for", "");
      purgeQueueTimeouts();
      int f =heapPopClosestFree();
      if(f!=-1 && !waitQ.empty()){
        String qp = waitQ.front().plate; waitQ.pop_front(); //handle waiting queue
        if(!commitIfAssignable(f, qp, now,false)){
          int f2 =heapPopClosestFree();
          if(f2!=-1 & commitIfAssignable(f2, qp, now, false)) {
            logDequeuedAssign(qp, f2);
            Serial.println("Queued car "+qp+" assigned to "+spotLabel(f2)+" (retry)");
          }else{
            waitQ.push_front({qp, now +MAX_WAIT_MS});
            Serial.println("Commit failed; re-queued "+qp);
          }
        }
        else { 
          logDequeuedAssign(qp, f);
          Serial.println("Queued car "+qp+" assigned to "+spotLabel(f));
        }
      } else if (f!=-1){
        heapPushIfFree(f);
      }
      updateLotState();
      Serial.println("Car left "+spotLabel(i));
    }
  }

  // cars arrivals
  if(now-lastArrivalMs_tracker >=ARRIVAL_INTERVAL_MS ||lastArrivalMs_tracker== 0){
    lastArrivalMs_tracker= now;
    arrivalCount ++;
    bool reservedCar_chooser=(arrivalCount%5==0 && !reservedindices.empty());
    int spotId=-1;
    String plate;
    if(reservedCar_chooser){
      int idx=-1;
      for(int i=0;i<reservedindices.size();i++){ //asign reserved
        int s=reservedindices[i];
        if(spotState[s]==RESERVED){ 
        idx=i; 
        break; 
        }
      }
      if(idx!=-1){
        spotId=reservedindices[idx];
        plate=reservedPlates[idx];
      }
    }
    if(spotId!=-1){ 
      if(!commitIfAssignable(spotId,plate, now, true)){
        //try again to see if something closer is free now
        int alt =heapPopClosestFree();
        if(alt==-1|| !commitIfAssignable(alt, plate, now,false)){
          purgeQueueTimeouts();
          if((int)waitQ.size() <MAX_Q){
            waitQ.push_back({plate, now+ MAX_WAIT_MS});
            logEnqueued(plate);
            markLotState("QUEUEING");
            Serial.println("Reserved spot not available; enqueued "+plate);
          } else 
          {
            logRejectedArrival(plate,"QUEUE_FULL");
            markLotState("FULL");
            Serial.println("Reserved spot not available; queue full. Rejected "+plate);
          }
        } 
        else 
        {
          Serial.println("Reserved car "+plate+" rerouted to "+spotLabel(alt));
          updateLotState();
        }
      } else {
        Serial.println("Reserved car "+plate+" arrived at "+spotLabel(spotId));
        updateLotState();
      }
    }
    else{
      plate = pickPlateForNormalArrival();
      if(isPlateAlreadyParked(plate)){
        Serial.println("Plate already parked, ignoring arrival: "+plate);
      } else {
        int id =heapPopClosestFree();
        if(id== -1){
          purgeQueueTimeouts(); //send to wait
          if((int)waitQ.size() <MAX_Q){
            waitQ.push_back({plate, now + MAX_WAIT_MS});
            logEnqueued(plate);
            markLotState("QUEUEING");
            Serial.println("Lot full. Enqueued "+plate);
          } else{
            logRejectedArrival(plate, "QUEUE_FULL"); //reject arrival in this case
            markLotState("FULL");
            Serial.println("Lot full & queue full. Rejected "+plate);
          }
        } 
        else if( !commitIfAssignable(id, plate, now, false)){
          int id2 = heapPopClosestFree();
          if(id2 ==-1 ||!commitIfAssignable(id2, plate, now, false)){
            purgeQueueTimeouts();
            if((int)waitQ.size() <MAX_Q){
              waitQ.push_back({plate, now +MAX_WAIT_MS});
              logEnqueued(plate);
              markLotState("QUEUEING");
              Serial.println("Commit failed; enqueued "+plate);
            } 
            else {
              logRejectedArrival(plate, "QUEUE_FULL");
              markLotState("FULL");
              Serial.println("Commit failed; queue full. Rejected "+plate);
            }
          } 
          else {
            Serial.println("Normal car "+plate+" arrived after retry at "+spotLabel(id2));
            updateLotState();
          }
        } 
        else {
          Serial.println("Normal car "+plate+" arrived at "+spotLabel(id));
          updateLotState();
        }
      }
    }
  }

  delay(5);
}
