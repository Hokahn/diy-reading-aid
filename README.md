# Reading Aid (Lesehilfe) for the Visually Impaired

This is a standalone electronic magnifier using a Raspberry Pi 3B and a Raspberry Pi Camera Module 3. It boots directly into a live, magnified camera feed on an external monitor. No login screen, desktop, keyboard, or mouse is required during normal operation. Four large metal buttons control the zoom and brightness/contrast. The reading material is moved by hand under the fixed, downward-facing camera.

<img width="1496" height="1297" alt="grafik" src="https://github.com/user-attachments/assets/6c405f7f-f8f1-4bee-a77c-d2cbb8600393" />


This was built for an elderly relative who is not comfortable with computers. The goal was an appliance that works like a TV: plug in the power, and the image appears.

## Hardware list

| Component | Description |
| --- | --- |
| Raspberry Pi 3 Model B, 1 GB RAM | Main computer |
| Raspberry Pi Camera Module 3 | Fixed, facing straight down |
| Dell 2001fp monitor | 4:3, 1600x1200 native, landscape orientation. Powers the Pi via its built-in USB port. No separate Pi power supply used |
| Micro-USB cable | Power: Dell 2001fp USB port to Pi micro-USB power input |
| DVI-to-HDMI cable | Video: Pi HDMI output to Dell 2001fp DVI input |
| 4x large metal push buttons | Zoom in, zoom out, brightness/contrast up, brightness/contrast down. Large buttons chosen for accessibility |
| Micro-SD card (16 GB+) | Boot / storage |
| 3D printed camera mount and button enclosure | Printed on a Bambu Lab A1, see 3D printed parts |
| Hookup wire | Buttons to GPIO header |

No internet connection is used or required. The device is fully offline.

## 3D printed parts

All enclosure and mount parts were designed with SE Student Edition for and printed on a Bambu Lab A1.

## Wiring and GPIO pinout

All four buttons are wired as simple momentary switches between a GPIO pin and Ground (GND), using the internal pull-up resistors of the Pi handled automatically by gpiozero.Button. No external resistors are needed.

| Function | GPIO (BCM) | Physical pin |
| --- | --- | --- |
| Zoom in | GPIO 17 | 11 |
| Zoom out | GPIO 27 | 13 |
| Brightness/contrast up | GPIO 22 | 15 |
| Brightness/contrast down | GPIO 23 | 16 |
| Ground | Any GND pin | 9 |

Each button: one leg to its GPIO pin, the other leg to any GND pin.

Video: Pi Camera Module 3 to CSI camera port via ribbon cable.

Pi HDMI out to DVI-to-HDMI cable to Dell 2001fp DVI-in.

Power: Dell 2001fp USB port to micro-USB cable to Pi power input.

The Pi receives power only when the monitor is powered. There is no separate power switch for the Pi itself. Every time the monitor is switched off, the Pi loses power immediately without a clean shutdown. See Protect the SD card, this is essential for this setup.

## How it works

The display powers the pi directly, so all can be turned on by the push of the monitor on button.

The camera feed is rendered directly to the screen via the DRM/KMS subsystem of the Linux kernel. No desktop environment or window manager is involved.

The camera reads out its full sensor resolution internally so that the digital zoom keeps as much detail as possible, while the main output stream is scaled down to the native resolution of the display to keep power draw manageable.

Focus is fixed because the camera-to-paper distance never changes. Autofocus is not used because it tends to hunt or lock onto the wrong distance at close range.

The four buttons are read via gpiozero. Holding a button down allows for repeated zoom or brightness steps instead of requiring many individual presses.

The program runs as a systemd service and restarts itself automatically if it crashes.

All 3d Print files are available, additionally there was a aluminum 25x25mm square pipe used.

<img width="983" height="548" alt="grafik" src="https://github.com/user-attachments/assets/c0fe8f1f-4032-4806-8862-6459b24167a8" />


## Software setup

### 1. Flash Raspberry Pi OS

Use Raspberry Pi OS Lite (64-bit). This avoids login-screen complexity, boots faster, and has fewer background services.

Download and open Raspberry Pi Imager. Choose OS: Raspberry Pi OS (other) then Raspberry Pi OS Lite (64-bit).

Click the advanced options and set:

Hostname: lesehilfe
Enable SSH
Username and password: lesehilfe
Wi-Fi: optional, only needed temporarily for setup

Write the image, insert the SD card into the Pi, and power it up.

### 2. First boot and update

```bash
ssh lesehilfe@lesehilfe.local
sudo apt update
sudo apt full-upgrade -y
sudo reboot

```

### 3. Install camera libraries

```bash
sudo apt install -y python3-picamera2 python3-gpiozero --no-install-recommends

```

Verify the camera is detected:

```bash
rpicam-hello --list-cameras

```

Expected output includes the imx708 sensor:

```text
0 : imx708 [4608x2592 10-bit RGGB] (/base/soc/i2c0mux/i2c@1/imx708@1a)

```

Note: older Raspberry Pi OS versions used libcamera-hello instead of rpicam-hello. If rpicam-hello is not found, try libcamera-hello, or install the tools explicitly with sudo apt install -y rpicam-apps.

### 4. Copy the program to the Pi

If you know how to use scp from your computer:

```bash
scp lesehilfe.py lesehilfe@lesehilfe.local:/home/lesehilfe/

```

Alternatively, SSH into the Pi and create the file directly:

```bash
sudo nano /home/lesehilfe/lesehilfe.py

```

Paste the full contents of lesehilfe.py from this repository, save, and exit.

### 5. Set display resolution and focus

Open the file and check these constants match your hardware:

```python
DISPLAY_WIDTH = 1600
DISPLAY_HEIGHT = 1200

```

This MUST match your monitor actual native resolution. To check:

```bash
sudo apt install -y libdrm-tests
modetest -M vc4 -c

```

Look for the connected connector and the mode marked preferred.

Focus is fixed and manual. Measure the real distance between the camera lens and the surface the newspaper lies on, then set the following variable:

```python
FESTER_FOKUS_DIOPTRIEN = 1 / 0.20

```

The 0.20 is the camera-to-paper distance in metres. Fine-tune in small steps after the first test run until text is sharp.

### 6. Manual test run

If the systemd service is already running, stop it first. Only one process can use the camera at a time:

```bash
sudo systemctl stop lesehilfe.service
sudo python3 /home/lesehilfe/lesehilfe.py

```

The camera feed should appear on the monitor. Test all four buttons. Stop with Ctrl+C.

### 7. Disable the login console

Raspberry Pi OS Lite runs a text login prompt on tty1 by default. This holds onto the display output and conflicts with the camera preview. You will see an error like ValueError: drmModeAddFB2 failed: Invalid argument.

Disable it permanently:

```bash
sudo systemctl stop getty@tty1
sudo systemctl disable getty@tty1

```

### 8. Hide the boot screen

This prevents the Pi from showing boot text before the camera feed starts.

```bash
sudo nano /boot/firmware/cmdline.txt

```

Append this to the end of the single line, separated by a space:

```text
quiet splash loglevel=0 logo.nologo vt.global_cursor_default=0 systemd.show_status=0

```

```bash
sudo nano /boot/firmware/config.txt

```

Append at the end:

```text
disable_splash=1

```

### 9. Autostart via systemd

Create the service file on the Pi:

```bash
sudo nano /etc/systemd/system/lesehilfe.service

```

```ini
[Unit]
Description=Lesehilfe Kamera Feed
After=local-fs.target

[Service]
ExecStart=/usr/bin/python3 /home/lesehilfe/lesehilfe.py
Restart=always
RestartSec=2
User=root

[Install]
WantedBy=multi-user.target

```

Save, exit, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lesehilfe.service

```

### 10. Reboot test

```bash
sudo reboot

```

After reboot the monitor should show the live camera feed directly. Reconnect via SSH to verify:

```bash
systemctl status lesehilfe.service

```

It should show active (running).

### 11. Power-saving settings

Power comes only from the monitor USB port. Keeping power draw low reduces the risk of under-voltage brownouts, which can cause crashes.

Disable unused hardware by adding to /boot/firmware/config.txt:

```text
dtoverlay=disable-wifi
dtoverlay=disable-bt
dtparam=act_led_trigger=none
dtparam=act_led_activelow=off
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off

```

Disable unused services:

```bash
sudo systemctl disable bluetooth hciuart wpa_supplicant
sudo systemctl disable triggerhappy
sudo systemctl disable ModemManager

```

Reduce CPU and GPU clock by adding to /boot/firmware/config.txt:

```text
arm_freq=800
core_freq=300
sdram_freq=400
over_voltage=0

```

Use the powersave CPU governor instead of the default ondemand governor:

```bash
echo "powersave" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

```

To make this persist across reboots, add it as a systemd service or append it to /etc/rc.local before the exit 0 line.

Check for under-voltage:

```bash
vcgencmd get_throttled
vcgencmd measure_temp

```

0x0 means no under-voltage has occurred since boot. Any other value means the Pi has been under-powered at some point.

### 12. Protect the SD card

The Pi loses power when the monitor is switched off. Repeated hard power-cuts can corrupt the SD card. Enable the overlay filesystem to make the root filesystem effectively read-only.

```bash
sudo raspi-config

```

Navigate to Performance Options or Advanced Options, then Overlay File System, enable it, and confirm the reboot.

While the overlay is active, file changes do not persist. To make changes: disable the overlay, edit, test, and re-enable the overlay.

## Known issues and fixes

| Issue | Fix |
| --- | --- |
| AttributeError: tuple object has no attribute width | Some picamera2 versions return PixelArrayActiveAreas as a plain tuple instead of a Rectangle object. The script handles both cases with a hasattr check. |
| ValueError: drmModeAddFB2 failed: Invalid argument | Caused by getty on tty1 holding the display, or under-voltage on the Pi. |
| Under-voltage detected | Current draw spikes exceed what the monitor USB port can deliver. Mitigate with power-saving settings, a thick USB cable, or reducing camera output resolution. |
| RuntimeError: Failed to acquire camera: Device or resource busy | Happens if you run the script manually while the systemd service is already running. Stop the service before manual testing. |
| Low effective zoom resolution or soft image | Digital zoom crops from an already-reduced image. Fix by requesting an explicit raw stream at the full sensor resolution alongside the smaller main output stream. |
| Autofocus not focusing correctly at close range | Continuous autofocus is unreliable at 10 to 20 cm distances. Switch to manual focus calibrated for the fixed distance. |
| Wrong username in default path | If you chose a different username during imaging, paths like /home/lesehilfe/ must use your actual home directory. |

## Maintenance and making further changes

Because the overlay filesystem is enabled, any file change is temporary until you disable it.

```bash
sudo raspi-config

```

Disable the Overlay File System and reboot.

```bash
nano /home/lesehilfe/lesehilfe.py

```

Make your changes, then restart the service:

```bash
sudo systemctl restart lesehilfe.service
journalctl -u lesehilfe.service -f

```

Re-enable the Overlay File System via raspi-config and reboot.
