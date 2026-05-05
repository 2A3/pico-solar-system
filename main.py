from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, PEN_RGB565
from pimoroni import Button, RGBLED
import time
import math
import gc
import machine
from micropython import const

#  Button Behavior:
#
#  Hold X + Y together = open timezone menu
#     A / B = change timezone
#     X = save
#     Y = cancel
#  A / B = adjust date
#  X / Y = brightness
#  A + B = reset date

# LED Behavior
#
# Connecting to WiFi       Blue (steady)
# NTP success              Green flash
# NTP failure retry        Red flash
# Normal running           Off 

# ===== Timezone settings =====
# Stored values are UTC offsets for US time zones.
# Example: Eastern Standard Time is UTC-5, Eastern Daylight Time is UTC-4.
TIMEZONES = [
    ("Eastern", 5, 4, True),
    ("Central", 6, 5, True),
    ("Mountain", 7, 6, True),
    ("Pacific", 8, 7, True),
    ("Arizona", 7, 7, False),
    ("UTC", 0, 0, False),
]

TZ_INDEX_FILE = "timezone.txt"
TZ_INDEX = 0
STD_OFFSET_HOURS = 5
DST_OFFSET_HOURS = 4
USE_DST = True

gc.enable()
backlight = 0.7
plusDays = 0
change = 0

TIME_STATUS = "?"

display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, rotate=0, pen_type=PEN_RGB565)
button_a = Button(12)
button_b = Button(13)
button_x = Button(14)
button_y = Button(15)
led = RGBLED(6, 7, 8)
led.set_rgb(0,0,0)


def load_timezone():
    global TZ_INDEX, STD_OFFSET_HOURS, DST_OFFSET_HOURS, USE_DST

    try:
        with open(TZ_INDEX_FILE, "r") as f:
            TZ_INDEX = int(f.read())
    except:
        TZ_INDEX = 0

    if TZ_INDEX < 0 or TZ_INDEX >= len(TIMEZONES):
        TZ_INDEX = 0

    name, std, dst, use_dst = TIMEZONES[TZ_INDEX]
    STD_OFFSET_HOURS = std
    DST_OFFSET_HOURS = dst
    USE_DST = use_dst
    print("Timezone:", name)


def save_timezone():
    with open(TZ_INDEX_FILE, "w") as f:
        f.write(str(TZ_INDEX))


def any_button_pressed():
    return button_a.is_pressed or button_b.is_pressed or button_x.is_pressed or button_y.is_pressed


def wait_for_buttons_released():
    while any_button_pressed():
        time.sleep(0.05)


def xy_buttons_held(hold_time=1.5):
    start = time.time()
    while button_x.is_pressed and button_y.is_pressed:
        if time.time() - start >= hold_time:
            wait_for_buttons_released()
            return True
        time.sleep(0.05)
    return False


def timezone_menu():
    global TZ_INDEX
    global change

    wait_for_buttons_released()

    while True:
        name, std, dst, use_dst = TIMEZONES[TZ_INDEX]

        display.set_pen(display.create_pen(0, 0, 0))
        display.clear()
        display.set_pen(display.create_pen(244, 170, 30))
        display.text("Timezone", 10, 8, 220, 3)
        display.set_pen(display.create_pen(130, 255, 100))
        display.text(name, 10, 42, 220, 3)
        display.set_pen(display.create_pen(180, 180, 180))
        display.text("A/B change", 10, 82, 220, 2)
        display.text("X save", 10, 102, 220, 2)
        display.text("Y cancel", 10, 122, 220, 2)
        display.update()

        if button_a.is_pressed:
            TZ_INDEX = (TZ_INDEX - 1) % len(TIMEZONES)
            wait_for_buttons_released()

        elif button_b.is_pressed:
            TZ_INDEX = (TZ_INDEX + 1) % len(TIMEZONES)
            wait_for_buttons_released()

        elif button_x.is_pressed:
            save_timezone()
            load_timezone()
            set_time()
            change = 3
            wait_for_buttons_released()
            return

        elif button_y.is_pressed:
            load_timezone()
            change = 3
            wait_for_buttons_released()
            return

        time.sleep(0.05)


def circle(xpos0, ypos0, rad):
    x = rad - 1
    y = 0
    dx = 1
    dy = 1
    err = dx - (rad << 1)
    while x >= y:
        display.pixel(xpos0 + x, ypos0 + y)
        display.pixel(xpos0 + y, ypos0 + x)
        display.pixel(xpos0 - y, ypos0 + x)
        display.pixel(xpos0 - x, ypos0 + y)
        display.pixel(xpos0 - x, ypos0 - y)
        display.pixel(xpos0 - y, ypos0 - x)
        display.pixel(xpos0 + y, ypos0 - x)
        display.pixel(xpos0 + x, ypos0 - y)
        if err <= 0:
            y += 1
            err += dy
            dy += 2
        if err > 0:
            x -= 1
            dx += 2
            err += dx - (rad << 1)

def show_startup_help():
    tz_name = TIMEZONES[TZ_INDEX][0]

    display.set_pen(display.create_pen(0, 0, 0))
    display.clear()

    display.set_pen(display.create_pen(244, 170, 30))
    display.text("Controls", 10, 4, 220, 3)

    display.set_pen(display.create_pen(180, 180, 180))
    display.text("A/B: +/- day", 10, 36, 220, 2)
    display.text("A+B: today", 10, 56, 220, 2)
    display.text("X/Y: brightness", 10, 76, 220, 2)
    display.text("Hold X+Y: TZ menu", 10, 96, 220, 2)

    display.set_pen(display.create_pen(130, 255, 100))
    display.text("TZ: " + tz_name, 10, 116, 120, 1)

    if TIME_STATUS == "W":
        status_text = "Time: WiFi"
    elif TIME_STATUS == "R":
        status_text = "Time: RTC"
    else:
        status_text = "Time: ?"

    display.text(status_text, 120, 116, 120, 1)

    display.update()

    start = time.time()
    while time.time() - start < 10:
        if button_a.is_pressed or button_b.is_pressed or button_x.is_pressed or button_y.is_pressed:
            break
        time.sleep(0.05)

    wait_for_buttons_released()
    
def led_wifi_connecting():
# Blue LED
    led.set_rgb(0, 0, 80)

def led_ntp_success():
# Green LED
    led.set_rgb(0, 120, 0)
    time.sleep(0.2)
    led.set_rgb(0, 0, 0)

def led_ntp_failure():
# Red LED
    led.set_rgb(120, 0, 0)
    time.sleep(0.3)
    led.set_rgb(0, 0, 0)    

def check_for_buttons():
    global backlight
    global plusDays
    global change

    # Hold X + Y together to open timezone menu.
    # Normal X/Y taps still adjust brightness as before.
    if button_x.is_pressed and button_y.is_pressed:
        if xy_buttons_held():
            timezone_menu()
            return

    if button_x.is_pressed:
        backlight += 0.05
        if backlight > 1:
            backlight = 1
        display.set_backlight(backlight)
    elif button_y.is_pressed:
        backlight -= 0.05
        if backlight < 0:
            backlight = 0
        display.set_backlight(backlight)
    if button_a.is_pressed and button_b.is_pressed:
        plusDays = 0
        change = 2
        time.sleep(0.2)
    elif button_a.is_pressed:
        plusDays += 86400
        change = 3
        time.sleep(0.05)
    elif button_b.is_pressed:
        plusDays -= 86400
        change = 3
        time.sleep(0.05)


def set_internal_time(utc_time):
    rtc_base_mem = const(0x4005c000)
    atomic_bitmask_set = const(0x2000)
    (year, month, day, hour, minute, second, wday, yday) = time.localtime(utc_time)
    machine.mem32[rtc_base_mem + 4] = (year << 12) | (month << 8) | day
    machine.mem32[rtc_base_mem + 8] = ((hour << 16) | (minute << 8) | second) | (((wday + 1) % 7) << 24)
    machine.mem32[rtc_base_mem + atomic_bitmask_set + 0xc] = 0x10


def main():
    global change
    import planets
    from pluto import Pluto
    load_timezone()
    set_time()
    show_startup_help()

    def draw_planets(HEIGHT, ti):
        PL_CENTER = (68, int(HEIGHT / 2))
        planets_dict = planets.coordinates(ti[0], ti[1], ti[2], ti[3], ti[4])
        # t = time.ticks_ms()
        display.set_pen(display.create_pen(255, 255, 0))
        display.circle(int(PL_CENTER[0]), int(PL_CENTER[1]), 4)
        for i, el in enumerate(planets_dict):
            r = 8 * (i + 1) + 2
            display.set_pen(display.create_pen(40, 40, 40))
            circle(PL_CENTER[0], PL_CENTER[1], r)
            feta = math.atan2(el[0], el[1])
            coordinates = (r * math.sin(feta), r * math.cos(feta))
            coordinates = (coordinates[0] + PL_CENTER[0], HEIGHT - (coordinates[1] + PL_CENTER[1]))
            for ar in range(0, len(planets.planets_a[i][0]), 5):
                x = planets.planets_a[i][0][ar] - 50 + coordinates[0]
                y = planets.planets_a[i][0][ar + 1] - 50 + coordinates[1]
                if x >= 0 and y >= 0:
                    display.set_pen(display.create_pen(planets.planets_a[i][0][ar + 2], planets.planets_a[i][0][ar + 3],
                                    planets.planets_a[i][0][ar + 4]))
                    display.pixel(int(x), int(y))
        # print("draw = " + str(time.ticks_diff(t, time.ticks_ms())))

    w = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    display.set_pen(display.create_pen(0, 0, 0))
    display.clear()
    display.update()
    display.set_backlight(0.7)
    gc.collect()

    HEIGHT = const(135)

    mi = -1
    pl = Pluto(display)

    seconds_absolute = time.time()
    ti = time.localtime(seconds_absolute + plusDays)
    da = ti[2]

    draw_planets(HEIGHT, ti)
    start_int = time.ticks_ms()
    while True:
        ticks_dif = time.ticks_diff(time.ticks_ms(), start_int)
        if ticks_dif >= 1000 or time.time() != seconds_absolute:
            seconds_absolute = time.time()
            ti = time.localtime(seconds_absolute + plusDays)
            start_int = time.ticks_ms()
            ticks_dif = 0
        if change > 0:
            ti = time.localtime(seconds_absolute + plusDays)
        if da != ti[2]:
            da = ti[2]
            change = 3

        if change > 0:
            if change == 1:
                display.set_pen(display.create_pen(0, 0, 0))
                display.clear()
                draw_planets(HEIGHT, ti)
                if plusDays > 0:
                    led.set_rgb(0, 50, 0)
                elif plusDays < 0:
                    led.set_rgb(50, 0, 0)
                else:
                    led.set_rgb(0, 0, 0)
                change = 0
            else:
                change -= 1

        display.set_pen(display.create_pen(0, 0, 0))
        display.rectangle(140, 0, 100, HEIGHT)
        display.rectangle(130, 0, 110, 35)
        display.rectangle(130, 93, 110, HEIGHT - 93)

        if mi != ti[4]:
            mi = ti[4]
            pl.reset()
        pl.step(ti[5], ticks_dif)
        pl.draw()

        display.set_pen(display.create_pen(244, 170, 30))
        display.text("%02d %s %d " % (ti[2], m[ti[1] - 1], ti[0]), 132, 7, 70, 2)
        display.set_pen(display.create_pen(65, 129, 50))
        display.text(w[ti[6]], 135, 93, 99, 2)
        display.set_pen(display.create_pen(130, 255, 100))
        display.text("%02d:%02d" % (ti[3], ti[4]), 132, 105, 99, 4)
        display.text(TIME_STATUS, 226, 2, 12, 1)
        display.update()
        check_for_buttons()
        time.sleep(0.01)
        
def local_offset_seconds(t):
    if not USE_DST:
        return STD_OFFSET_HOURS * 3600

    year = time.localtime(t)[0]

    def first_sunday(year, month):
        for day in range(1, 8):
            if time.localtime(time.mktime((year, month, day, 0, 0, 0, 0, 0)))[6] == 6:
                return day

    march_second_sunday = first_sunday(year, 3) + 7
    november_first_sunday = first_sunday(year, 11)

    dst_start = time.mktime((year, 3, march_second_sunday, 2, 0, 0, 0, 0, 0))
    dst_end = time.mktime((year, 11, november_first_sunday, 2, 0, 0, 0, 0, 0))

    if dst_start <= t < dst_end:
        return DST_OFFSET_HOURS * 3600
    else:
        return STD_OFFSET_HOURS * 3600

def set_time():
    global TIME_STATUS
    try:
        import wifi_config
        set_time_ntp(wifi_config)
    except Exception as e:
        print("WiFi/NTP failed, using DS3231 fallback:", e)
        import ds3231
        ds = ds3231.ds3231()
        utc = ds.read_time()
        set_internal_time(utc + local_offset_seconds(utc))
        TIME_STATUS = "R"
        
def set_time_ntp(wifi_config):
    global TIME_STATUS
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print("Connecting to:", wifi_config.ssid)
    wlan.connect(wifi_config.ssid, wifi_config.key)
    led_wifi_connecting()
  
    for _ in range(12):  # about 60 seconds
        if wlan.isconnected():
            break
        print("Waiting for connection...")
        time.sleep(5)

    if not wlan.isconnected():
        raise RuntimeError("WiFi connection timeout")
        led.set_rgb(0, 0, 0)
    
    print(wlan.ifconfig())
    
    print("Pico clock:", time.localtime())
    print("Setting time via ntp...")
    import ntptime
    ntpsuccess = False
    for _ in range(12):  # about 60 seconds
        try:
            ntptime.settime()

            utc = time.time()
            local = utc - local_offset_seconds(utc)
            set_internal_time(local)
            
            TIME_STATUS = "W"
            led_ntp_success()
            
            try:
                import ds3231
                ds = ds3231.ds3231()
                ds.set_time(utc)
                print("DS3231 updated from NTP")
            except Exception as e:
                print("RTC update skipped:", e)

            print("UTC time: ", time.localtime(utc))
            print("Local time: ", time.localtime(local))

            ntpsuccess = True
            break
        except:
            print("NTP failure. Retrying.")
            led_ntp_failure()
            time.sleep(5)

    if not ntpsuccess:
        raise RuntimeError("NTP timeout")

time.sleep(0.5)
main()


