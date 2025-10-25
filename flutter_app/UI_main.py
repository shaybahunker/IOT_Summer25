#this is a UI file to integrate with out arduino code. its goal i to vizualize the data from Firebase, to see it more clearly,
#and to simulate teh led lights. Note: spot 0 is the actual sesor-based spot, its not part of the simulation, its in this UI
#to emphasize led color changing and to explain how the virtual sesors will work if they were real, like the sensor
#in spot 0.
import sys,os, time,json, math
from typing import Dict, Tuple,Optional,List
from dataclasses import dataclass

import random

import requests
from PySide6 import QtCore, QtGui,QtWidgets

#here we set the data in order to connect to the real time data base in firebase
FIREBASE_API_KEY="AIzaSyCp9MhvXE68oYGD4RGYb3NRs2B9z8bk0-M" #firebase api key
FIREBASE_URL="https://iot-group9-smart-parking-default-rtdb.firebaseio.com" #firebase url
FIREBASE_USER= "iotgroupp9@gmail.com" #this is a user so we can autenticate the log in to firebase, so no third side will interrupt the data sending
FIREBASE_PASSWORD = "Noa55643"#user pass

CHECK_FB_UPDATES= 2000 #how often the ui checks for firebase updates
CAR_FRAME_MS=120#how often car goes to next frame
CAR_SPEED_PX_S=260.0 #pixel per second in car moving
SPOT_W,SPOT_H= 46, 84 #parking spot width and height
LED_RADIOS =7 # the radios of the led
PIC_PAD= 40 #padding aroud picture
CAR_PIXEL_WIDTH= 26
FONT_TO_USE ="Arial"

# the code uses grid to place parking spots, this is its setup for sizes and placing
CELL_W= 70#width x step
CELL_H = 120 #height y step
TOP_LEFT_SPOT1= QtCore.QPointF(240, 160)#top left spot, floor 1
FLOOR_GAP =260#gap of the floor
TOP_LEFT_SPOT2 =QtCore.QPointF(TOP_LEFT_SPOT1.x()+ 5*CELL_W+FLOOR_GAP,TOP_LEFT_SPOT1.y())#top left spot, floor 2
BACKGROUND_PIC= "background.png" #the asphalt in the background

#grid to pixel position
def grid_point(x,y,floor,center: bool=False) ->QtCore.QPointF:
    start_floor =TOP_LEFT_SPOT1 if floor == 1 else TOP_LEFT_SPOT2
    px = start_floor.x()+ (x-1) *CELL_W #adjusting to match the layout
    py = start_floor.y() + (y-1) * CELL_H
    if center:
        px +=SPOT_W/2
        py+= SPOT_H/2
    return QtCore.QPointF(px,py)

ENTRANCE_POINT= grid_point(0,0, 1,True) #where cars enter from

#setting the path for the ramp to do between floors (1 to 2)
RAMP_Y=TOP_LEFT_SPOT1.y()+2.5 * CELL_H #2.5 to get to the middle of the row
RAMP_X1=TOP_LEFT_SPOT1.x()+5*CELL_W+12 #adjust
RAMP_X2= TOP_LEFT_SPOT2.x() -12
RAMP_HEIGHT=24
#setting colors up
COLOR_LINE = QtGui.QColor(160,160,160)
COLOR_LED_FREE =QtGui.QColor(50, 205,50)
COLOR_LED_TAKEN=QtGui.QColor(220,20, 60)
COLOR_LED_RESERVED=QtGui.QColor(255, 165, 0)
BOARD_COLOR=QtGui.QColor(18, 20,24)
BOARD_COLOR_TEXT =QtGui.QColor(240,240, 245)
COLOR_ARROW= QtGui.QColor(230,230, 80)

#this is a class to create firebase client, we will use it to read data from firebase and then update the ui
class FirebaseClient:
    def __init__(self, api_key: str, db_url: str, email: str, password: str):
        self.api_key =api_key
        self.db_url= db_url.rstrip('/')
        self.email= email
        self.password= password
        self.id_token:Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.last_login_ts =0.0  # was _last_login_ts

    def sign_in(self): #used to sign in to the user for authentication
        url= f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.api_key}"
        payload = {"email": self.email, "password": self.password, "returnSecureToken": True}
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        self.id_token = data["idToken"]
        self.refresh_token = data.get("refreshToken")
        self.last_login_ts = time.time()

    def is_token_missing_or_old(self):
        if not self.id_token or not (time.time() -self.last_login_ts) <=3000:
            self.sign_in()

    def get_json(self, path: str):
        self.is_token_missing_or_old()
        url = f"{self.db_url}/{path.lstrip('/')}"
        r = requests.get(url,
                         params={"auth": self.id_token, "ns": None},
                         headers={"Cache-Control": "no-cache"},
                         timeout=10)
        r.raise_for_status()
        data = r.json() if r.text else {}
        print("fetching..", path,"->", type(data).__name__, str(data)[:200])
        return data

    def patch_json(self, path: str, data: dict):
        self.is_token_missing_or_old()
        url = f"{self.db_url}/{path.lstrip('/')}"
        params = {"auth":self.id_token}
        r = requests.patch(url,params=params, json=data, timeout=10)
        r.raise_for_status()
        return r.json() if r.text else {}



#now here we will configure the geometry and layout of the parking lot. a picture of the layout can be seen when running the code/in the project's poster
PARKING_LAYOUT_CORDS: Dict[int, Tuple[int,int,int]] = { #(x,y,floor)
    0: (0, 1,1),  #spot 0 is a special one. it is the only spot using the real sensor, for presenting purposes
    #floor 1:
    1:(1,1,1), 2: (2, 1,1), 3:(3,1, 1), 4:(4, 1, 1), 5:(5, 1, 1),
    6: (1,2, 1), 7:(2, 2,1), 8:(3, 2,1), 9: (4,2, 1), 10:(5,2,1),
    11: (1, 3, 1), 12: (2, 3, 1), 13: (3, 3, 1), 14: (4, 3,1), 15: (5, 3, 1),
    16: (1, 4, 1), 17: (2, 4,1), 18: (3, 4, 1), 19: (4, 4,1), 20: (5, 4, 1),
    21: (1, 5, 1), 22: (2, 5,1), 23: (3, 5, 1), 24:(4, 5,1), 25: (5,5, 1),
    # floor 2:
    26: (1, 1,2), 27: (2, 1, 2), 28: (3, 1, 2), 29:(4,1, 2), 30: (5, 1, 2),
    31: (1, 2,2), 32: (2,2, 2), 33: (3, 2, 2), 34: (4, 2, 2), 35: (5, 2, 2),
    36: (1, 3, 2), 37: (2,3, 2), 38:(3, 3, 2), 39:(4, 3, 2), 40:(5,3, 2),
    41:(1, 4,2), 42: (2, 4,2), 43: (3, 4, 2), 44:(4, 4, 2), 45: (5, 4, 2),
    46: (1,5, 2), 47:(2, 5, 2), 48:(3, 5, 2), 49: (4, 5, 2),
}
#this calss saves al sata related to single parking spot
@dataclass
class parkingSpot:
    idx:int
    parking_rect: QtWidgets.QGraphicsRectItem
    parking_led_ligh: QtWidgets.QGraphicsEllipseItem
    label_item:QtWidgets.QGraphicsSimpleTextItem
    car_in_parking: Optional[QtWidgets.QGraphicsPixmapItem] =None


class parkingManager(QtWidgets.QGraphicsScene):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.backg_pm = QtGui.QPixmap(BACKGROUND_PIC) #background config
        self.backg_itm = QtWidgets.QGraphicsPixmapItem()
        self.backg_itm.setZValue(-1000)  # behind everything
        self.addItem(self.backg_itm)
        #there are 8 different cars images in the project directory, here they are loaded
        self.car_frames: List[QtGui.QPixmap] = []
        for i in range(8):
            carPic = f"car_{i}.png"
            if os.path.exists(carPic):
                pm =QtGui.QPixmap(carPic)
            else:
                pm = QtGui.QPixmap(36,18)
                pm.fill(QtCore.Qt.transparent)
                p = QtGui.QPainter(pm)
                p.setRenderHint(QtGui.QPainter.Antialiasing)
                p.setBrush(QtGui.QBrush(QtGui.QColor(130,180,220)))
                p.setPen(QtCore.Qt.NoPen)
                p.drawRoundedRect(0, 0,36, 18, 4 , 4)
                p.end()
            self.car_frames.append(pm)

        # car spot &led config
        self.spots:Dict[int, parkingSpot] = {}
        self.curr_car_state_led: Dict[int, str] ={}
        self.plate_by_spot:Dict[int, str] ={}

        #configurations for board
        path=QtGui.QPainterPath()
        path.addRoundedRect(0, 0,1200, 70, 12,12) #parking spots layout
        self.board_rect=QtWidgets.QGraphicsPathItem(path)
        self.board_rect.setBrush(QtGui.QBrush(BOARD_COLOR))
        self.board_rect.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.addItem(self.board_rect)
        self.board_text =self.addSimpleText("Welcome to IoT Parking Lot!")
        self.board_text.setBrush(BOARD_COLOR_TEXT)
        font_to_use =QtGui.QFont(FONT_TO_USE,20, QtGui.QFont.Bold)
        self.board_text.setFont(font_to_use)
        self.board_text.setPos(16,18)
        self.draw_parking()
        self.setSceneRect(self.itemsBoundingRect().adjusted(-PIC_PAD, -PIC_PAD, PIC_PAD, PIC_PAD))
        self.fit_background_img_png()
        self.animations: List["CarAnimator"] =[]

    def get_Spot_from_topleft(self, idx: int) -> QtCore.QPointF:
        x, y,floor =PARKING_LAYOUT_CORDS.get(idx, (1,1,1))
        return grid_point(x, y, floor,False)

    def get_spot_center(self, idx: int) ->QtCore.QPointF:
        return grid_point(PARKING_LAYOUT_CORDS[idx][0],
                          PARKING_LAYOUT_CORDS[idx][1],PARKING_LAYOUT_CORDS[idx][2],True)

    def led_pos(self, get_Spot_from_topleft: QtCore.QPointF) ->QtCore.QPointF:
        return QtCore.QPointF(get_Spot_from_topleft.x() +SPOT_W/2 -LED_RADIOS, get_Spot_from_topleft.y() -18) #adjustments so it will be in middle

    def drawing_grid(self, origin: QtCore.QPointF, title: str): #drawing the grid
        pen = QtGui.QPen(COLOR_LINE, 2)
        grid_w = 5*CELL_W
        grid_h =5*CELL_H
        self.addRect(origin.x()-14, origin.y()-20,grid_w+28,grid_h+40, pen)

        for c in range(6):
            x = origin.x() +c*CELL_W
            self.addLine(x, origin.y()-10, x, origin.y()+grid_h+10, QtGui.QPen(COLOR_LINE, 1, QtCore.Qt.DashLine))
        for r in range(6):
            y = origin.y() + r*CELL_H
            self.addLine(origin.x()-10, y, origin.x()+grid_w+10, y, QtGui.QPen(COLOR_LINE, 1, QtCore.Qt.DashLine))

        t = self.addSimpleText(title)
        t.setBrush(QtGui.QColor(210,210,220))
        t.setFont(QtGui.QFont(FONT_TO_USE, 12, QtGui.QFont.Bold))
        t.setPos(origin.x()-10, origin.y()-48)

    #"ramp" to go between floor 1 and 2
    def draw_ramp_horizontal(self):
        y = RAMP_Y -RAMP_HEIGHT/2
        ramp = QtWidgets.QGraphicsRectItem(QtCore.QRectF(RAMP_X1, y, RAMP_X2- RAMP_X1, RAMP_HEIGHT))
        ramp.setBrush(QtGui.QBrush(QtGui.QColor(70, 70,80)))
        ramp.setPen(QtGui.QPen(QtGui.QColor(110,110,120), 2,QtCore.Qt.DashDotLine))
        self.addItem(ramp)
        label = self.addSimpleText("RAMP-->")
        label.setBrush(QtGui.QColor(220,220,230))
        label.setFont(QtGui.QFont(FONT_TO_USE, 10, QtGui.QFont.DemiBold))
        label.setPos((RAMP_X1 + RAMP_X2)/2 - 24, y- 22)

    def draw_entrance(self): # entry point, cars get from here to first floor
        enter_parking = ENTRANCE_POINT
        e_circle = self.addEllipse(enter_parking.x()-10, enter_parking.y()-10, 20, 20,
                                   QtGui.QPen(QtGui.QColor(240,240,240), 2),
                                   QtGui.QBrush(QtGui.QColor(60,140,60)))
        label = self.addSimpleText("Entrance (0,0)")
        label.setBrush(QtGui.QColor(230,230,235))
        label.setFont(QtGui.QFont(FONT_TO_USE, 11,QtGui.QFont.DemiBold))
        label.setPos(enter_parking.x()-58,enter_parking.y()-40)

    #drawing the whole parking lot to vizualize the Ui
    def draw_parking(self):
        # Guides and labels
        self.drawing_grid(TOP_LEFT_SPOT1,"Floor 1")
        self.drawing_grid(TOP_LEFT_SPOT2,"Floor 2")
        self.draw_entrance()
        self.draw_ramp_horizontal()
        for i in range(50):
            pos = self.get_Spot_from_topleft(i)
            rect = QtCore.QRectF(pos.x(), pos.y(), SPOT_W, SPOT_H)
            ritem = self.addRect(rect, QtGui.QPen(COLOR_LINE, 2), QtGui.QBrush(QtGui.QColor(54,58,64)))
            led_pos_pt = self.led_pos(pos)
            led = self.addEllipse(led_pos_pt.x(), led_pos_pt.y(), LED_RADIOS*2,LED_RADIOS*2,
                                  QtGui.QPen(QtCore.Qt.NoPen), QtGui.QBrush(COLOR_LED_FREE))
            lab = self.addSimpleText(f"P{str(i).zfill(2)}")
            lab.setBrush(QtGui.QColor(220,220,225))
            lab.setFont(QtGui.QFont(FONT_TO_USE, 10, QtGui.QFont.DemiBold))
            lab.setPos(rect.x()+6,rect.y()+4)
            self.spots[i] = parkingSpot(i, ritem, led, lab)
            self.curr_car_state_led[i] ="FREE"
            self.plate_by_spot[i] = ""

    def fit_background_img_png(self):
        rect = self.sceneRect()
        if not self.backg_pm.isNull():
            pm = self.backg_pm.scaled(int(rect.width()), int(rect.height()),QtCore.Qt.KeepAspectRatioByExpanding,QtCore.Qt.SmoothTransformation)
            self.backg_itm.setPixmap(pm)
            self.backg_itm.setPos(rect.topLeft())

    def set_curr_car_state_led(self, idx: int, state: str): #led color for car parking spot
        spot = self.spots[idx]
        color = COLOR_LED_RESERVED
        if state == "FREE":
            color=COLOR_LED_FREE
        elif state == "TAKEN":
            color =COLOR_LED_TAKEN
        spot.parking_led_ligh.setBrush(QtGui.QBrush(color))
        self.curr_car_state_led[idx] =state

    def show_board(self, text: str):
        self.board_text.setText(text)

    # animate the arrival of the car to the Spot
    def car_arrive_anima(self, plate, spot_idx,was_reserved):
        start =ENTRANCE_POINT
        x, y, floor =PARKING_LAYOUT_CORDS.get(spot_idx, (1,1,1))
        col_center_FLOOR1 =grid_point(x, y=1, floor=1, center=True).x()
        col_center_FLOOR2 = grid_point(x, y=1, floor=2, center=True).x()
        row_center_FLOOR1 = grid_point(1, y, floor=1, center=True).y()
        row_center_FLOOR2 = grid_point(1, y, floor=2, center=True).y()

        target = self.get_spot_center(spot_idx)
        path_points = [start]

        if not floor == 1:
            path_points.append(QtCore.QPointF(start.x(), RAMP_Y))
            ramp_x_mid = (RAMP_X1 + RAMP_X2) / 2
            path_points.append(QtCore.QPointF(ramp_x_mid, RAMP_Y))
            path_points.append(QtCore.QPointF(ramp_x_mid, row_center_FLOOR2))
            path_points.append(QtCore.QPointF(col_center_FLOOR2, row_center_FLOOR2))

        else:
            path_points.append(QtCore.QPointF(col_center_FLOOR1, start.y()))
            path_points.append(QtCore.QPointF(col_center_FLOOR1, row_center_FLOOR1))
        path_points.append(target)
        arrow = ArrowPath(path_points, COLOR_ARROW)
        self.addItem(arrow)
        car_index = random.randint(0, len(self.car_frames) - 1)
        pm = self.car_frames[car_index].scaledToWidth(CAR_PIXEL_WIDTH, QtCore.Qt.SmoothTransformation)
        car = AnimatedCar([pm],CAR_FRAME_MS)
        car.setData(0,car_index)
        car.setTransformOriginPoint(car.boundingRect().center())
        car.setPos(start- QtCore.QPointF(car.boundingRect().width()/2, car.boundingRect().height()/2))
        self.addItem(car)
        car.start()
        if was_reserved:
            self.show_board(f"Reserved car {plate}. Go to P{str(spot_idx).zfill(2)}")
        else:
            self.show_board(f"Car {plate}. Go to P{str(spot_idx).zfill(2)}")

        anim = CarAnimator(
            car, path_points,
            speed_px_s=CAR_SPEED_PX_S,
            on_done=lambda:self.finish_parking(car, spot_idx, arrow)
        )
        self.animations.append(anim)
        anim.start()

    def finish_parking(self, car_in_parking: "AnimatedCar", spot_idx,arrow_item: QtWidgets.QGraphicsItem):
        self.removeItem(arrow_item)
        if self.spots[spot_idx].car_in_parking:
            self.removeItem(self.spots[spot_idx].car_in_parking)
        car_index = car_in_parking.data(0) or 0
        pm = self.car_frames[car_index].scaledToWidth(CAR_PIXEL_WIDTH, QtCore.Qt.SmoothTransformation)
        static_car = QtWidgets.QGraphicsPixmapItem(pm)
        rect = self.spots[spot_idx].parking_rect.rect()
        static_car.setPos(rect.center().x() - pm.width() / 2, rect.center().y() - pm.height() / 2)
        static_car.setRotation(0)
        self.addItem(static_car)
        self.spots[spot_idx].car_in_parking = static_car
        self.removeItem(car_in_parking)

    def clear_parked(self, spot_idx: int):
        it =self.spots[spot_idx].car_in_parking
        if it:
            self.removeItem(it)
            self.spots[spot_idx].car_in_parking = None

#arrows shoeing the car where to go
class ArrowPath(QtWidgets.QGraphicsPathItem):
    def __init__(self, pts, color):
        path =QtGui.QPainterPath(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        super().__init__(path)
        pen =QtGui.QPen(color, 3)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        self.setPen(pen)
        self.setZValue(2)

# class to gather all car data
class AnimatedCar(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, frames: List[QtGui.QPixmap], frame_ms: int):
        super().__init__()
        self.frames=frames
        self.frame_ms= frame_ms #how long to change
        self.idx =0
        self.setPixmap(self.frames[self.idx])
        self.timer =QtCore.QTimer()
        self.timer.timeout.connect(self.next_frame)
        self.setZValue(3)

    def start(self):
        self.timer.start(self.frame_ms)

    def stop(self):
        self.timer.stop()

    def next_frame(self):
        self.idx = (self.idx +1) %len(self.frames)
        self.setPixmap(self.frames[self.idx])

def angle_deg_from_vec(dx, dy) ->float: #make sure the car drives in the arrow direction
    # Going right/left → car looks vertical
    # Going up/down → car looks horizontal
    if abs(dx) > abs(dy):
        return 90 if dx> 0 else -90   #from horizontal to vertical
    else:
        return 0 if dy > 0 else 180    # from vertical to horizontal


class CarAnimator(QtCore.QObject): #animating the car obj
    def __init__(self, item: QtWidgets.QGraphicsItem, pts: List[QtCore.QPointF], speed_px_s: float, on_done=None):
        super().__init__()
        self.item =item
        self.path_pts= pts
        self.speed =speed_px_s
        self.on_done = on_done
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.setInterval(16)  # ~60 FPS
        self.seg_idx =0
        self.seg_len = 0.0
        self.seg_dir = QtCore.QPointF(0, 0)
        self.seg_a =QtCore.QPointF(pts[0])
        self.seg_b= QtCore.QPointF(pts[1])
        self.car_needPrepare_segment(0)
        self.item.setPos(self.seg_a - self.item.boundingRect().center())
        self.apply_rotation(self.seg_dir)

    def car_needPrepare_segment(self, idx: int):
        self.seg_idx = idx
        self.seg_a =self.path_pts[idx]
        self.seg_b=self.path_pts[idx+1]
        dx = self.seg_b.x() - self.seg_a.x()
        dy = self.seg_b.y() -self.seg_a.y()
        length =math.hypot(dx, dy)
        self.seg_len = max(0.0, length)
        if length <1e-6: # meaning "almost the same spot"
            self.seg_dir = QtCore.QPointF(0, 0)
        else:
            self.seg_dir = QtCore.QPointF(dx/length, dy/length)

    def apply_rotation(self, dir_vec: QtCore.QPointF):
        if abs(dir_vec.x()) <1e-6 and abs(dir_vec.y()) <1e-6: #meaning "almost the same spot"
            return
        angle =angle_deg_from_vec(dir_vec.x(), dir_vec.y())
        self.item.setRotation(angle)

    #start car timer
    def start(self):
        self.timer.start()

    def tick(self):
        #how much more distance to go left
        pos_center = self.item.pos() +self.item.boundingRect().center()
        rem = math.hypot(self.seg_b.x()-pos_center.x(), self.seg_b.y()-pos_center.y())
        if self.seg_len< 1e-6 or rem < 1e-3: # meaning "almost the same spot"
            self.item.setPos(self.seg_b - self.item.boundingRect().center())
            if self.seg_idx >= len(self.path_pts)-2:
                self.timer.stop()
                if self.on_done: self.on_done()
                return
            self.car_needPrepare_segment(self.seg_idx + 1) #next one
            self.apply_rotation(self.seg_dir)

        # Move by step; if we overshoot, carry into next segments (no pause)
        step = self.speed * (self.timer.interval()/1000.0)
        while step > 0 and True:
            pos_center = self.item.pos() + self.item.boundingRect().center()
            to_end = math.hypot(self.seg_b.x()-pos_center.x(), self.seg_b.y()-pos_center.y())
            if to_end <= step + 1e-6:
                # Jump to end of this segment
                self.item.setPos(self.seg_b - self.item.boundingRect().center())
                step -= to_end
                # Next segment?
                if self.seg_idx >= len(self.path_pts)-2:
                    self.timer.stop()
                    if self.on_done: self.on_done()
                    return
                self.car_needPrepare_segment(self.seg_idx + 1)
                self.apply_rotation(self.seg_dir)
            else:
                x = pos_center.x() +self.seg_dir.x()*step
                y = pos_center.y() + self.seg_dir.y()*step
                self.item.setPos(QtCore.QPointF(x,y)- self.item.boundingRect().center())
                step = 0.0

# the main windown of the UI
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, fb: FirebaseClient):
        super().__init__()
        self.fire_Base =fb
        self.setWindowTitle("Smart Parking UI")
        self.resize(1700,950)
        self.scene =parkingManager()
        view = QtWidgets.QGraphicsView(self.scene)
        view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.setCentralWidget(view)
        self.prev_states: Dict[int, Dict[str, Optional[str]]] = {}
        self.poll_timer =QtCore.QTimer()
        self.poll_timer.timeout.connect(self.parking_data_from_fireBase)
        self.poll_timer.start(CHECK_FB_UPDATES)
        QtCore.QTimer.singleShot(200, self.parking_data_from_fireBase)

    def apply_spot_state(self, idx, node ):
        state = node.get("state", "FREE")
        plate = node.get("plate", "") or ""
        reserved_for = node.get("reserved_for", "") or ""
        self.scene.set_curr_car_state_led(idx, state)
        prev = self.prev_states.get(idx)
        if prev is None:
            #spot is taken
            if state =="TAKEN":
                car_index= 0
                pm =self.scene.car_frames[car_index].scaledToWidth(CAR_PIXEL_WIDTH, QtCore.Qt.SmoothTransformation)
                static_car = QtWidgets.QGraphicsPixmapItem(pm)
                rect =self.scene.spots[idx].parking_rect.rect()
                static_car.setPos(rect.center().x() -pm.width()/2, rect.center().y()- pm.height()/2)
                self.scene.addItem(static_car)
                self.scene.spots[idx].car_in_parking =static_car
                self.scene.plate_by_spot[idx] = plate
            self.prev_states[idx] = {"state": state, "plate": plate, "reserved_for": reserved_for}
            return

        #we announce car arriving and animating it
        if prev["state"] in ("FREE","RESERVED") and state =="TAKEN":
            was_reserved = bool(prev.get("reserved_for") and prev.get("reserved_for") == plate)
            self.scene.car_arrive_anima(plate or "(unknown)", idx, was_reserved)
            self.scene.plate_by_spot[idx] = plate
        if prev["state"] == "TAKEN" and state == "FREE":
            self.scene.clear_parked(idx)
            self.scene.plate_by_spot[idx] = ""
        self.prev_states[idx] = {"state": state, "plate": plate, "reserved_for": reserved_for}

    def parking_data_from_fireBase(self): #get the data of parkings from firebase
        try:
            data = self.fire_Base.get_json("/spots.json") or {}
        except Exception as e:
            print("Firebase error reading:", e)
            self.scene.show_board("Firebase error reading")
            return

        def node_at(i):
            if isinstance(data, list):
                return (data[i] or {}) if i < len(data) else {}
            if isinstance(data, dict):
                return data.get(str(i), {}) or {}
            return {}

        for i in range(50):
            node = node_at(i)
            state = node.get("state", "FREE")
            plate = node.get("plate", "") or ""
            reserved_for = node.get("reserved_for", "") or ""
            if i ==0:
                self.scene.set_curr_car_state_led(i, state)
                self.prev_states[i] = {"state": state, "plate": plate, "reserved_for": reserved_for}
                continue
            self.scene.set_curr_car_state_led(i, state)

            prev = self.prev_states.get(i, {})
            if prev.get("state") in ("FREE", "RESERVED") and state == "TAKEN":
                was_reserved = reserved_for == (plate or "")
                self.scene.car_arrive_anima(plate or "(plate)", i, was_reserved)
            elif prev.get("state") == "TAKEN" and state == "FREE":
                self.scene.clear_parked(i)

            self.prev_states[i] = {"state": state, "plate": plate, "reserved_for": reserved_for}

#Main func, enty poit for the ui
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    fb = FirebaseClient(FIREBASE_API_KEY,FIREBASE_URL, FIREBASE_USER,FIREBASE_PASSWORD)
    try:
        fb.sign_in()
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Firebase login failed", str(e))
        sys.exit(1)

    window_main = MainWindow(fb)
    window_main.show()
    sys.exit(app.exec())
