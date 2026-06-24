"""
CuePlot Digital Projection E-Vision native protocol driver.

Implements the documented ASCII control protocol from:
Digital Projection Protocol Guides Rev F (115-482F, October 2016),
specifically the "E-Vision Laser 7500 & 8500 Series" section.

Wire format:
    *command = value<CR>
    *command ?<CR>
    *command<CR>

Transport:
    TCP port 7000

Notes:
    - This is a native Digital Projection driver, not PJLink.
    - The source protocol in hand is explicitly for E-Vision Laser 7500/8500.
      Nearby E-Vision models may be compatible, but they are unverified.
"""

from __future__ import annotations

import asyncio
from typing import Any

from server.drivers.base import BaseDriver
from server.utils.logger import get_logger

log = get_logger(__name__)


def _sanitize_key(command_name: str) -> str:
    return (
        command_name.replace(".", "_")
        .replace("/", "_")
        .replace("-", "_")
        .lower()
    )


def _enum_param(label: str, values: list[Any]) -> dict[str, Any]:
    return {"type": "enum", "label": label, "values": values}


def _int_param(label: str, minimum: int | None = None, maximum: int | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"type": "integer", "label": label}
    if minimum is not None:
        data["min"] = minimum
    if maximum is not None:
        data["max"] = maximum
    return data


def _str_param(label: str) -> dict[str, Any]:
    return {"type": "string", "label": label}


SET_COMMANDS: dict[str, dict[str, Any]] = {
    "set_input": {
        "protocol": "input",
        "params": {"value": _enum_param("Input", [0, 1, 2, 3, 4, 5, 6, 7])},
        "help": "Set active input. 0=HDMI1, 1=HDMI2, 2=VGA, 3=COMP, 4=DVI, 5=DisplayPort, 6=HDBaseT, 7=3GSDI.",
    },
    "set_test_pattern": {
        "protocol": "test.pattern",
        "params": {"value": _int_param("Pattern", 0, 11)},
        "help": "Select built-in test pattern.",
    },
    "set_lens_lock": {
        "protocol": "lens.lock",
        "params": {"value": _enum_param("Lens Lock", [0, 1])},
        "help": "Enable or disable lens lock.",
    },
    "set_lens_load": {
        "protocol": "lens.load",
        "params": {"value": _int_param("Lens Memory", 1, 10)},
        "help": "Recall lens memory slot.",
    },
    "set_lens_save": {
        "protocol": "lens.save",
        "params": {"value": _int_param("Lens Memory", 1, 10)},
        "help": "Store current lens position to memory slot.",
    },
    "set_lens_clear": {
        "protocol": "lens.clear",
        "params": {"value": _int_param("Lens Memory", 1, 10)},
        "help": "Clear lens memory slot.",
    },
    "set_pic_mode": {
        "protocol": "pic.mode",
        "params": {"value": _enum_param("Picture Mode", [0, 1, 2])},
    },
    "set_db_on": {
        "protocol": "db.on",
        "params": {"value": _enum_param("Dynamic Black", [0, 1])},
    },
    "set_brightness": {"protocol": "brightness", "params": {"value": _int_param("Brightness", 0, 200)}},
    "set_contrast": {"protocol": "contrast", "params": {"value": _int_param("Contrast", 0, 200)}},
    "set_gamma": {"protocol": "gamma", "params": {"value": _int_param("Gamma", 0, 7)}},
    "set_saturation": {"protocol": "saturation", "params": {"value": _int_param("Saturation", 0, 200)}},
    "set_hue": {"protocol": "hue", "params": {"value": _int_param("Hue", 0, 200)}},
    "set_sharpness": {"protocol": "sharpness", "params": {"value": _int_param("Sharpness", 0, 200)}},
    "set_nr_temporal": {"protocol": "nr.temporal", "params": {"value": _int_param("Temporal NR", 0, 3)}},
    "set_nr_block": {"protocol": "nr.block", "params": {"value": _int_param("Block NR", 0, 3)}},
    "set_nr_mosquito": {"protocol": "nr.mosquito", "params": {"value": _int_param("Mosquito NR", 0, 3)}},
    "set_nr_hori": {"protocol": "nr.hori", "params": {"value": _int_param("Horizontal NR", 0, 3)}},
    "set_nr_vert": {"protocol": "nr.vert", "params": {"value": _int_param("Vertical NR", 0, 3)}},
    "set_nr_reset": {"protocol": "nr.reset", "params": {"value": _int_param("Reset NR", 0, 3)}},
    "set_h_position": {"protocol": "h.position", "params": {"value": _int_param("Horizontal Position", 0, 200)}},
    "set_v_position": {"protocol": "v.position", "params": {"value": _int_param("Vertical Position", 0, 200)}},
    "set_vga_phase": {"protocol": "vga.phase", "params": {"value": _int_param("VGA Phase", 0, 200)}},
    "set_tracking": {"protocol": "tracking", "params": {"value": _int_param("Tracking", 0, 200)}},
    "set_sync_level": {"protocol": "sync.level", "params": {"value": _int_param("Sync Level", 0, 200)}},
    "set_freeze": {"protocol": "freeze", "params": {"value": _enum_param("Freeze", [0, 1])}},
    "set_color_space": {"protocol": "color.space", "params": {"value": _int_param("Color Space", 0, 4)}},
    "set_color_temp": {"protocol": "color.temp", "params": {"value": _int_param("Color Temp", 0, 5)}},
    "set_color_mode": {"protocol": "color.mode", "params": {"value": _int_param("Color Mode", 0, 3)}},
    "set_color_max": {"protocol": "color.max", "params": {"value": _int_param("ColorMax", 0, 3)}},
    "set_red_lift": {"protocol": "red.lift", "params": {"value": _int_param("Red Lift", 0, 200)}},
    "set_green_lift": {"protocol": "green.lift", "params": {"value": _int_param("Green Lift", 0, 200)}},
    "set_blue_lift": {"protocol": "blue.lift", "params": {"value": _int_param("Blue Lift", 0, 200)}},
    "set_red_gain": {"protocol": "red.gain", "params": {"value": _int_param("Red Gain", 0, 200)}},
    "set_green_gain": {"protocol": "green.gain", "params": {"value": _int_param("Green Gain", 0, 200)}},
    "set_blue_gain": {"protocol": "blue.gain", "params": {"value": _int_param("Blue Gain", 0, 200)}},
    "set_auto_test_ptrn": {"protocol": "auto.test.ptrn", "params": {"value": _enum_param("Auto Test Pattern", [0, 1])}},
    "set_user_std_rx": {"protocol": "user.std.rx", "params": {"value": _int_param("User Std R X", 550, 750)}},
    "set_user_std_ry": {"protocol": "user.std.ry", "params": {"value": _int_param("User Std R Y", 250, 450)}},
    "set_user_std_gx": {"protocol": "user.std.gx", "params": {"value": _int_param("User Std G X", 200, 400)}},
    "set_user_std_gy": {"protocol": "user.std.gy", "params": {"value": _int_param("User Std G Y", 400, 750)}},
    "set_user_std_bx": {"protocol": "user.std.bx", "params": {"value": _int_param("User Std B X", 50, 250)}},
    "set_user_std_by": {"protocol": "user.std.by", "params": {"value": _int_param("User Std B Y", 0, 120)}},
    "set_user_std_wx": {"protocol": "user.std.wx", "params": {"value": _int_param("User Std W X", 200, 400)}},
    "set_user_std_wy": {"protocol": "user.std.wy", "params": {"value": _int_param("User Std W Y", 250, 450)}},
    "set_aspect_ratio": {"protocol": "aspect.ratio", "params": {"value": _int_param("Aspect Ratio", 0, 8)}},
    "set_digi_zoom": {"protocol": "digi.zoom", "params": {"value": _int_param("Digital Zoom", -100, 100)}},
    "set_digi_pan": {"protocol": "digi.pan", "params": {"value": _int_param("Digital Pan", -320, 320)}},
    "set_digi_scan": {"protocol": "digi.scan", "params": {"value": _int_param("Digital Scan", -200, 200)}},
    "set_overscan": {"protocol": "overscan", "params": {"value": _int_param("Overscan", 0, 2)}},
    "set_active_warp": {"protocol": "active.warp", "params": {"value": _int_param("Active Warp", 0, 4)}},
    "set_h_keystone": {"protocol": "h.keystone", "params": {"value": _int_param("Horizontal Keystone", -600, 600)}},
    "set_v_keystone": {"protocol": "v.keystone", "params": {"value": _int_param("Vertical Keystone", -400, 400)}},
    "set_rotation": {"protocol": "rotation", "params": {"value": _int_param("Rotation", -100, 100)}},
    "set_h_pin_barrel": {"protocol": "h.pin.barrel", "params": {"value": _int_param("H Pin Barrel", -150, 300)}},
    "set_v_pin_barrel": {"protocol": "v.pin.barrel", "params": {"value": _int_param("V Pin Barrel", -150, 300)}},
    "set_4corner_ulx": {"protocol": "4corner.ulx", "params": {"value": _int_param("4 Corner ULX", -192, 192)}},
    "set_4corner_uly": {"protocol": "4corner.uly", "params": {"value": _int_param("4 Corner ULY", -120, 120)}},
    "set_4corner_urx": {"protocol": "4corner.urx", "params": {"value": _int_param("4 Corner URX", -192, 192)}},
    "set_4corner_ury": {"protocol": "4corner.ury", "params": {"value": _int_param("4 Corner URY", -120, 120)}},
    "set_4corner_llx": {"protocol": "4corner.llx", "params": {"value": _int_param("4 Corner LLX", -192, 192)}},
    "set_4corner_lly": {"protocol": "4corner.lly", "params": {"value": _int_param("4 Corner LLY", -120, 120)}},
    "set_4corner_lrx": {"protocol": "4corner.lrx", "params": {"value": _int_param("4 Corner LRX", -192, 192)}},
    "set_4corner_lry": {"protocol": "4corner.lry", "params": {"value": _int_param("4 Corner LRY", -120, 120)}},
    "set_blanking_top": {"protocol": "blanking.top", "params": {"value": _int_param("Blanking Top", 0, 360)}},
    "set_blanking_bottom": {"protocol": "blanking.bottom", "params": {"value": _int_param("Blanking Bottom", 0, 360)}},
    "set_blanking_left": {"protocol": "blanking.left", "params": {"value": _int_param("Blanking Left", 0, 534)}},
    "set_blanking_right": {"protocol": "blanking.right", "params": {"value": _int_param("Blanking Right", 0, 534)}},
    "set_cust_wp_write": {"protocol": "cust.wp.write", "params": {"value": _enum_param("Custom Warp File", [1, 2])}},
    "set_cust_wp_clear": {"protocol": "cust.wp.clear", "params": {"value": _enum_param("Custom Warp File", [1, 2])}},
    "set_cust_wp_send": {"protocol": "cust.wp.send", "params": {"value": _enum_param("Custom Warp Send", [0, 1, 2])}},
    "set_warp_cust": {"protocol": "warp.cust", "params": {"value": _enum_param("Custom Warp Active", [0, 1, 2])}},
    "set_eb_stat": {"protocol": "eb.stat", "params": {"value": _enum_param("Edge Blend", [0, 1])}},
    "set_eb_adl": {"protocol": "eb.adl", "params": {"value": _enum_param("ADL", [0, 1])}},
    "set_eb_top": {"protocol": "eb.top", "params": {"value": _str_param("Edge Blend Top (0 or 100-500)")}},
    "set_eb_bottom": {"protocol": "eb.bottom", "params": {"value": _str_param("Edge Blend Bottom (0 or 100-500)")}},
    "set_eb_left": {"protocol": "eb.left", "params": {"value": _str_param("Edge Blend Left (0 or 100-500)")}},
    "set_eb_right": {"protocol": "eb.right", "params": {"value": _str_param("Edge Blend Right (0 or 100-500)")}},
    "set_eb_blu_top": {"protocol": "eb.blu.top", "params": {"value": _int_param("Top Black Level", 0, 32)}},
    "set_eb_blu_bottom": {"protocol": "eb.blu.bottom", "params": {"value": _int_param("Bottom Black Level", 0, 32)}},
    "set_eb_blu_left": {"protocol": "eb.blu.left", "params": {"value": _int_param("Left Black Level", 0, 32)}},
    "set_eb_blu_right": {"protocol": "eb.blu.right", "params": {"value": _int_param("Right Black Level", 0, 32)}},
    "set_eb_all": {"protocol": "eb.all", "params": {"value": _int_param("All Black Level", 0, 32)}},
    "set_eb_red": {"protocol": "eb.red", "params": {"value": _int_param("Edge Blend Channel", 0, 255)}},
    "set_3d_format": {"protocol": "3d.format", "params": {"value": _int_param("3D Format", 0, 5)}},
    "set_3d_dlplink": {"protocol": "3d.dlplink", "params": {"value": _enum_param("3D DLP Link", [0, 1])}},
    "set_3d_dominance": {"protocol": "3d.dominance", "params": {"value": _enum_param("3D Dominance", [0, 1])}},
    "set_3d_darktime": {"protocol": "3d.darktime", "params": {"value": _int_param("3D Dark Time", 0, 3)}},
    "set_3d_syncoffset": {"protocol": "3d.syncoffset", "params": {"value": _int_param("3D Sync Offset", 0, 200)}},
    "set_3d_syncref": {"protocol": "3d.syncref", "params": {"value": _enum_param("3D Sync Ref", [0, 1])}},
    "set_laser_mode": {"protocol": "laser.mode", "params": {"value": _int_param("Laser Mode", 0, 2)}},
    "set_laser_power": {"protocol": "laser.power", "params": {"value": _int_param("Laser Power", 20, 100)}},
    "set_altitude": {"protocol": "altitude", "params": {"value": _int_param("Altitude", 1, 2)}},
    "set_cooling_condition": {"protocol": "cooling.condition", "params": {"value": _int_param("Cooling Condition", 0, 3)}},
    "set_orientation": {"protocol": "orientation", "params": {"value": _int_param("Orientation", 0, 4)}},
    "set_screen_setting": {"protocol": "screen.setting", "params": {"value": _int_param("Screen Setting", 0, 2)}},
    "set_auto_poweroff": {"protocol": "auto.poweroff", "params": {"value": _enum_param("Auto Power Off", [0, 1])}},
    "set_auto_poweron": {"protocol": "auto.poweron", "params": {"value": _enum_param("Auto Power On", [0, 1])}},
    "set_startup_logo": {"protocol": "startup.logo", "params": {"value": _enum_param("Startup Logo", [0, 1])}},
    "set_blank_screen": {"protocol": "blank.screen", "params": {"value": _int_param("Blank Screen", 0, 3)}},
    "set_schedule_power": {"protocol": "schedule.power", "params": {"value": _enum_param("Schedule Power", [0, 1])}},
    "set_schedule1_on_day": {"protocol": "schedule1.on.day", "params": {"value": _str_param("Schedule1 On Day Bitmask")}},
    "set_schedule1_off_day": {"protocol": "schedule1.off.day", "params": {"value": _str_param("Schedule1 Off Day Bitmask")}},
    "set_schedule1_on_time": {"protocol": "schedule1.on.time", "params": {"value": _str_param("Schedule1 On Time HH:MM")}},
    "set_schedule1_off_time": {"protocol": "schedule1.off.time", "params": {"value": _str_param("Schedule1 Off Time HH:MM")}},
    "set_schedule2_on_day": {"protocol": "schedule2.on.day", "params": {"value": _str_param("Schedule2 On Day Bitmask")}},
    "set_schedule2_off_day": {"protocol": "schedule2.off.day", "params": {"value": _str_param("Schedule2 Off Day Bitmask")}},
    "set_schedule2_on_time": {"protocol": "schedule2.on.time", "params": {"value": _str_param("Schedule2 On Time HH:MM")}},
    "set_schedule2_off_time": {"protocol": "schedule2.off.time", "params": {"value": _str_param("Schedule2 Off Time HH:MM")}},
    "set_date": {"protocol": "date", "params": {"value": _str_param("Date yyyy/MM/dd")}},
    "set_time_zone": {"protocol": "time.zone", "params": {"value": _int_param("Time Zone", -11, 12)}},
    "set_time_adjust": {"protocol": "time.adjust", "params": {"value": _str_param("Time HH:MM")}},
    "set_trig_1": {"protocol": "trig.1", "params": {"value": _int_param("Trigger 1", 0, 13)}},
    "set_trig_2": {"protocol": "trig.2", "params": {"value": _int_param("Trigger 2", 0, 13)}},
    "set_auto_source": {"protocol": "auto.source", "params": {"value": _enum_param("Auto Source", [0, 1])}},
    "set_ir_enable": {"protocol": "ir.enable", "params": {"value": _enum_param("IR Enable", [0, 1])}},
    "set_ir_code": {"protocol": "ir.code", "params": {"value": _str_param("IR Code 00-99")}},
    "set_osd_lang": {"protocol": "osd.lang", "params": {"value": _int_param("OSD Language", 0, 4)}},
    "set_osd_menupos": {"protocol": "osd.menupos", "params": {"value": _int_param("OSD Menu Position", 0, 4)}},
    "set_osd_trans": {"protocol": "osd.trans", "params": {"value": _int_param("OSD Transparency", 0, 3)}},
    "set_osd_timer": {"protocol": "osd.timer", "params": {"value": _int_param("OSD Timer", 0, 3)}},
    "set_osd_msgbox": {"protocol": "osd.msgbox", "params": {"value": _enum_param("OSD Message Box", [0, 1])}},
    "set_recall_mem": {"protocol": "recall.mem", "params": {"value": _int_param("Recall Memory", 0, 4)}},
    "set_save_mem": {"protocol": "save.mem", "params": {"value": _int_param("Save Memory", 0, 3)}},
    "set_network_mode": {"protocol": "network.mode", "params": {"value": _enum_param("Network Mode", [0, 1])}},
    "set_lan_power": {"protocol": "lan.power", "params": {"value": _enum_param("LAN Power", [0, 1])}},
    "set_lan_dhcp": {"protocol": "lan.dhcp", "params": {"value": _enum_param("LAN DHCP", [0, 1])}},
    "set_lan_ip": {"protocol": "lan.ip", "params": {"value": _str_param("LAN IP")}},
    "set_lan_subnet": {"protocol": "lan.subnet", "params": {"value": _str_param("LAN Subnet")}},
    "set_lan_gateway": {"protocol": "lan.gateway", "params": {"value": _str_param("LAN Gateway")}},
    "set_lan_dns": {"protocol": "lan.dns", "params": {"value": _str_param("LAN DNS")}},
    "set_lan_amx": {"protocol": "lan.amx", "params": {"value": _enum_param("AMX Discovery", [0, 1])}},
    "set_pip_mode": {"protocol": "pip.mode", "params": {"value": _enum_param("PIP Mode", [0, 1])}},
    "set_pip_input": {"protocol": "pip.input", "params": {"value": _int_param("PIP Input", 0, 6)}},
    "set_pip_position": {"protocol": "pip.position", "params": {"value": _int_param("PIP Position", 0, 4)}},
    "set_power": {"protocol": "power", "params": {"value": _enum_param("Power", [0, 1])}},
    "set_shutter": {"protocol": "shutter", "params": {"value": _enum_param("Shutter", [0, 1])}},
}

EXECUTE_COMMANDS: dict[str, dict[str, Any]] = {
    "zoom_in": {"protocol": "zoom.in"},
    "zoom_out": {"protocol": "zoom.out"},
    "focus_near": {"protocol": "focus.near"},
    "focus_far": {"protocol": "focus.far"},
    "lens_center": {"protocol": "lens.center"},
    "lens_up": {"protocol": "lens.up"},
    "lens_down": {"protocol": "lens.down"},
    "lens_left": {"protocol": "lens.left"},
    "lens_right": {"protocol": "lens.right"},
    "resync": {"protocol": "resync"},
    "gainlift_reset": {"protocol": "gainlift.reset"},
    "user_std_reset": {"protocol": "user.std.reset"},
    "user_target_reset": {"protocol": "user.target.reset"},
    "user2_target_reset": {"protocol": "user2.target.reset"},
    "user_p7_rst": {"protocol": "user.p7.rst"},
    "hsg_reset": {"protocol": "hsg.reset"},
    "digi_room_reset": {"protocol": "digi.room.rst"},
    "blanking_reset": {"protocol": "blanking.reset"},
    "warp_reset": {"protocol": "warp.reset"},
    "eb_reset": {"protocol": "eb.reset"},
    "ir_code_reset": {"protocol": "ir.code.rst"},
    "pip_swap": {"protocol": "pip.swap"},
    "factory_reset": {"protocol": "factory.reset"},
}

QUERY_PROTOCOLS: list[str] = [
    "input", "test.pattern", "lens.lock", "lens.save", "lens.type",
    "pic.mode", "db.on", "brightness", "contrast", "gamma", "saturation",
    "hue", "sharpness", "nr.temporal", "nr.block", "nr.mosquito",
    "nr.hori", "nr.vert", "nr.reset", "h.position", "v.position",
    "vga.phase", "tracking", "sync.level", "freeze", "color.space",
    "color.temp", "color.mode", "color.max", "red.lift", "green.lift",
    "blue.lift", "red.gain", "green.gain", "blue.gain", "auto.test.ptrn",
    "user.std.rx", "user.std.ry", "user.std.gx", "user.std.gy",
    "user.std.bx", "user.std.by", "user.std.wx", "user.std.wy",
    "user.target.rx", "user.target.ry", "user.target.gx", "user.target.gy",
    "user.target.bx", "user.target.by", "user.target.wx", "user.target.wy",
    "user.target.cx", "user.target.cy", "user.target.mx", "user.target.my",
    "user.target.yx", "user.target.yy", "user2.target.rx", "user2.target.ry",
    "user2.target.gx", "user2.target.gy", "user2.target.bx", "user2.target.by",
    "user2.target.wx", "user2.target.wy", "user2.target.cx", "user2.target.cy",
    "user2.target.mx", "user2.target.my", "user2.target.yx", "user2.target.yy",
    "hsg.hue.r", "hsg.hue.g", "hsg.hue.b", "hsg.hue.c", "hsg.hue.m", "hsg.hue.y",
    "hsg.sat.r", "hsg.sat.g", "hsg.sat.b", "hsg.sat.c", "hsg.sat.m", "hsg.sat.y",
    "hsg.gain.r", "hsg.gain.g", "hsg.gain.b", "hsg.gain.c", "hsg.gain.m", "hsg.gain.y",
    "aspect.ratio", "digi.zoom", "digi.pan", "digi.pan.bound", "digi.scan",
    "digi.scan.bound", "overscan", "active.warp", "h.keystone", "v.keystone",
    "rotation", "h.pin.barrel", "v.pin.barrel", "4corner.ulx", "4corner.uly",
    "4corner.urx", "4corner.ury", "4corner.llx", "4corner.lly", "4corner.lrx",
    "4corner.lry", "blanking.top", "blanking.bottom", "blanking.left",
    "blanking.right", "cust.wp.send", "cust.wp.ck.sum", "warp.cust", "eb.stat",
    "eb.adl", "eb.top", "eb.bottom", "eb.left", "eb.right", "eb.blu.top",
    "eb.blu.bottom", "eb.blu.left", "eb.blu.right", "eb.all", "eb.red",
    "3d.format", "3d.dlplink", "3d.dominance", "3d.darktime", "3d.syncoffset",
    "3d.syncref", "laser.mode", "laser.power", "laser.hours", "altitude",
    "cooling.condition", "orientation", "screen.setting", "auto.poweroff",
    "auto.poweron", "startup.logo", "blank.screen", "schedule.power",
    "schedule1.on.day", "schedule1.off.day", "schedule1.on.time",
    "schedule1.off.time", "schedule2.on.day", "schedule2.off.day",
    "schedule2.on.time", "schedule2.off.time", "date", "time.zone",
    "time.adjust", "trig.1", "trig.2", "auto.source", "ir.enable",
    "ir.code", "osd.lang", "osd.menupos", "osd.trans", "osd.timer",
    "osd.msgbox", "recall.mem", "network.mode", "lan.power", "lan.dhcp",
    "lan.ip", "lan.subnet", "lan.gateway", "lan.dns", "lan.mac", "lan.amx",
    "pip.mode", "pip.input", "pip.position", "model.name", "serial",
    "sw.version", "act.source", "signal", "h.refresh", "v.refresh",
    "pixel.clock", "atmos.alti", "atmos.pressure", "ac.voltage", "g.ceiling",
    "g.portrait", "g.tilt", "altitude.info", "laser.power.info", "ti", "ti2",
    "tc", "tb1", "tb2", "fan1_3", "fan4_6", "fan7_9", "fan10_12", "fan13_15",
    "fan16_18", "water.pump", "power", "shutter", "total.hours", "status",
    "errcode",
]


def _build_commands() -> dict[str, Any]:
    commands: dict[str, Any] = {}
    for name, spec in SET_COMMANDS.items():
        commands[name] = {
            "label": name.replace("_", " ").title(),
            "params": spec["params"],
            "help": spec.get("help", f"Set {spec['protocol']}."),
        }
    for name, spec in EXECUTE_COMMANDS.items():
        commands[name] = {
            "label": name.replace("_", " ").title(),
            "params": {},
            "help": f"Execute {spec['protocol']}.",
        }
    for protocol in QUERY_PROTOCOLS:
        commands[f"query_{_sanitize_key(protocol)}"] = {
            "label": f"Query {protocol}",
            "params": {},
            "help": f"Query current value of {protocol}.",
        }
    commands["query_all_status"] = {
        "label": "Query All Status",
        "params": {},
        "help": "Query a broad set of power, source, optical, geometry, network, and diagnostic values.",
    }
    return commands


class DigitalProjectionEVisionDriver(BaseDriver):
    DRIVER_INFO = {
        "id": "digital_projection_evision",
        "name": "Digital Projection E-Vision Native",
        "manufacturer": "Digital Projection",
        "category": "projector",
        "version": "2.0.0",
        "author": "CuePlot",
        "description": (
            "Native ASCII protocol driver for Digital Projection E-Vision Laser "
            "7500/8500 based on Protocol Guides Rev F (115-482F)."
        ),
        "source_url": "https://www.digitalprojection.com/",
        "tags": ["projector", "digital projection", "e-vision", "native", "tcp", "rs232"],
        "verified": False,
        "simulated": False,
        "protocols": ["tcp", "ascii"],
        "ports": [7000],
        "transport": "tcp",
        "delimiter": "\r",
        "discovery": {
            "port_open": [7000],
            "manufacturer_alias": ["digital projection", "digital projection international"],
            "hostname": ["(?i)^e-?vision.*$", "(?i)^digital-?projection.*$", "(?i)^dp-.*$"],
        },
        "compatible_models": [
            {
                "manufacturer": "Digital Projection",
                "models": ["E-Vision Laser 7500", "E-Vision Laser 8500"],
                "confidence": "documented",
                "notes": "Implements the native protocol documented in Digital Projection Protocol Guides Rev F (115-482F, October 2016).",
            }
        ],
        "help": {
            "overview": (
                "Native Digital Projection driver using the documented ASCII command protocol. "
                "Exposes power, shutter, inputs, test patterns, lens, image, color, geometry, "
                "edge blend, 3D, laser, scheduling, network, PIP, information, and diagnostics."
            ),
            "setup": (
                "1. Put the projector on the same network as CuePlot.\n"
                "2. Confirm the projector TCP control port is 7000.\n"
                "3. Add the device with its IP address and port 7000.\n"
                "4. Use Refresh / Query All Status to verify communications.\n"
                "5. Build macros only after power, shutter, input, and lens commands respond correctly."
            ),
        },
        "default_config": {
            "host": "",
            "port": 7000,
            "poll_interval": 15,
        },
        "config_schema": {
            "host": {"type": "string", "required": True, "label": "IP Address or Hostname"},
            "port": {"type": "integer", "default": 7000, "label": "TCP Control Port"},
            "poll_interval": {"type": "integer", "default": 15, "min": 0, "label": "Poll Interval (sec)"},
        },
        "state_variables": {
            "power": {"type": "enum", "values": ["off", "on"], "label": "Power"},
            "status": {"type": "enum", "values": ["standby", "warm_up", "imaging", "cooling", "error"], "label": "Status"},
            "shutter": {"type": "enum", "values": ["open", "close"], "label": "Shutter"},
            "input": {"type": "integer", "label": "Input"},
            "act_source": {"type": "integer", "label": "Active Source"},
            "model_name": {"type": "string", "label": "Model Name"},
            "serial": {"type": "string", "label": "Serial Number"},
            "sw_version": {"type": "string", "label": "Software Version"},
            "signal": {"type": "string", "label": "Signal"},
            "laser_hours": {"type": "string", "label": "Laser Hours"},
            "laser_power": {"type": "integer", "label": "Laser Power"},
            "laser_mode": {"type": "integer", "label": "Laser Mode"},
            "total_hours": {"type": "string", "label": "Total Hours"},
            "errcode": {"type": "string", "label": "Error Code"},
            "lan_ip": {"type": "string", "label": "LAN IP"},
            "lan_mac": {"type": "string", "label": "LAN MAC"},
            "last_response": {"type": "string", "label": "Last Response"},
            "last_error": {"type": "string", "label": "Last Error"},
        },
        "commands": _build_commands(),
    }

    STATUS_MAP = {
        "0": "standby",
        "1": "warm_up",
        "2": "imaging",
        "3": "cooling",
        "4": "error",
    }

    POWER_MAP = {"0": "off", "1": "on"}
    SHUTTER_MAP = {"0": "open", "1": "close"}

    async def connect(self) -> None:
        await super().connect()
        await self.poll()

    async def disconnect(self) -> None:
        await super().disconnect()

    async def _send_line(self, line: str) -> None:
        if not self.transport or not self.transport.connected:
            raise ConnectionError(f"[{self.device_id}] Not connected")
        await self.transport.send((line + "\r").encode("ascii"))

    async def send_command(self, command: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}

        if command == "query_all_status":
            await self.poll()
            return

        spec = SET_COMMANDS.get(command)
        if spec is not None:
            value = params.get("value")
            if value is None:
                raise ValueError(f"Command {command} requires 'value'")
            await self._send_line(f"*{spec['protocol']} = {value}")
            return

        spec = EXECUTE_COMMANDS.get(command)
        if spec is not None:
            await self._send_line(f"*{spec['protocol']}")
            return

        if command.startswith("query_"):
            protocol = command[len("query_"):].replace("_", ".")
            # special cases where underscores are part of flattened names
            protocol = protocol.replace("4corner.", "4corner.")
            protocol = protocol.replace("3d.", "3d.")
            protocol = protocol.replace("eb.", "eb.")
            protocol = protocol.replace("lan.", "lan.")
            if protocol in QUERY_PROTOCOLS:
                await self._send_line(f"*{protocol} ?")
                return
            # recover exact protocol names from known query set
            for candidate in QUERY_PROTOCOLS:
                if _sanitize_key(candidate) == command[len("query_"):]:
                    await self._send_line(f"*{candidate} ?")
                    return

        raise ValueError(f"Unknown command: {command}")

    async def on_data_received(self, data: bytes) -> None:
        text = data.decode("ascii", errors="ignore").strip()
        if not text:
            return

        self.set_state("last_response", text)

        lowered = text.lower()
        if lowered.startswith("nak") or lowered.startswith("nack"):
            self.set_state("last_error", text)
            log.warning("[%s] NAK: %s", self.device_id, text)
            return

        payload = text
        if lowered.startswith("ack"):
            payload = text[3:].strip()
        elif lowered.startswith("nack"):
            payload = text[4:].strip()
        elif lowered.startswith("*"):
            payload = text[1:].strip()
        elif not any(ch in text for ch in ("=",)):
            log.debug("[%s] Unrecognized response: %s", self.device_id, text)
            return

        if "=" not in payload:
            return

        cmd, value = payload.split("=", 1)
        cmd = cmd.strip()
        value = value.strip()
        key = _sanitize_key(cmd)

        if cmd == "power":
            self.set_state("power", self.POWER_MAP.get(value, value))
        elif cmd == "status":
            self.set_state("status", self.STATUS_MAP.get(value, value))
        elif cmd == "shutter":
            self.set_state("shutter", self.SHUTTER_MAP.get(value, value))
        elif cmd in {"input", "act.source", "laser.power", "laser.mode"}:
            try:
                self.set_state(key, int(value))
            except ValueError:
                self.set_state(key, value)
        elif cmd == "lan.ip":
            self.set_state("lan_ip", value)
        elif cmd == "lan.mac":
            self.set_state("lan_mac", value)
        elif cmd == "model.name":
            self.set_state("model_name", value)
        else:
            self.set_state(key, value)

    async def poll(self) -> None:
        common_queries = [
            "power", "status", "shutter", "input", "act.source", "model.name",
            "serial", "sw.version", "signal", "laser.hours", "laser.power",
            "laser.mode", "total.hours", "errcode", "lan.ip", "lan.mac",
        ]
        for protocol in common_queries:
            await self._send_line(f"*{protocol} ?")
            await asyncio.sleep(0.08)
