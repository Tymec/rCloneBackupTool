import sys
import configparser
import subprocess
import threading
import time
import os
import win32api
import win32con
import win32gui_struct
import win32gui

_cwd = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(_cwd, "config.ini")
LOG_PATH    = os.path.join(_cwd, "logs")
TRAY_ICON   = os.path.join(_cwd, "logo.ico")
TRAY_TEXT   = "rClone Backup"
CONFIG_TEMPLATE = "[JOB_1]\nNAME\t\t\t\t\t= Default\nPATH\t\t\t\t\t= C:\\Users\nREMOTE\t\t\t\t\t= GoogleDrive:Users\n\n[OPTIONS]\nMODE\t\t\t\t\t= copy\n\n[PARAMETERS]\nUPDATE\t\t\t\t\t= 1\nVERBOSE\t\t\t\t\t= 1\n\n[ARGUMENTS]\nTRANSFERS\t\t\t\t= 10\nCHECKERS\t\t\t\t= 20\nCONTIMEOUT\t\t\t\t= 60s\nTIMEOUT\t\t\t\t\t= 300s\nRETRIES\t\t\t\t\t= 3\nLOW-LEVEL-RETRIES\t\t= 10\nSTATS\t\t\t\t\t= 1s"

current_program = win32gui.GetForegroundWindow()
win32gui.ShowWindow(current_program , win32con.SW_HIDE)

class SysTray(threading.Thread):
    QUIT = 'QUIT'
    SPECIAL_ACTIONS = [QUIT]

    FIRST_ID = 1023

    def __init__(self, icon, hover_text, menu_options, on_quit=None, default_menu_index=None, window_class_name=None):
        threading.Thread.__init__(self)
        self.icon = icon
        self.hover_text = hover_text
        self.on_quit = on_quit
        self._is_alive = True
        
        self.menu_options = menu_options.append(('Quit', None, self.QUIT))
        self._next_action_id = self.FIRST_ID
        self.menu_actions_by_id = set()
        self.menu_options = self._add_ids_to_menu_options(list(menu_options))
        self.menu_actions_by_id = dict(self.menu_actions_by_id)
        del self._next_action_id

        self.default_menu_index = (default_menu_index or 0)
        self.window_class_name = window_class_name or "SysTrayIconPy"

    @staticmethod
    def _force_kill():
        current_pid = os.getpid()
        os.system("taskkill /pid %s /f" % current_pid)

    def run(self):
        message_map = {
            win32gui.RegisterWindowMessage("TaskbarCreated"): self.restart,
            win32con.WM_DESTROY: self.destroy,
            win32con.WM_COMMAND: self.command,
            win32con.WM_USER+20: self.notify
        }

        # Register the Window class.
        wc = win32gui.WNDCLASS()
        hinst = wc.hInstance = win32gui.GetModuleHandle(None)
        wc.lpszClassName = self.window_class_name
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW;
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32con.COLOR_WINDOW
        wc.lpfnWndProc = message_map # could also specify a wndproc.
        class_atom = win32gui.RegisterClass(wc)

        # Create the Window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(
            class_atom,
            self.window_class_name,
            style,
            0,
            0,
            win32con.CW_USEDEFAULT,
            win32con.CW_USEDEFAULT,
            0,
            0,
            hinst,
            None
        )
        win32gui.UpdateWindow(self.hwnd)
        self.notify_id = None
        self.refresh_icon()

        #win32gui.PumpMessages()
        while self._is_alive:
            win32gui.PumpWaitingMessages()
        win32gui.DestroyWindow(self.hwnd)

    @staticmethod
    def non_string_iterable(obj):
        try:
            iter(obj)
        except TypeError:
            return False
        else:
            return not isinstance(obj, str)

    def create_notification(self, title, message, duration=10):
        hinst = win32gui.GetModuleHandle(None)
        if os.path.isfile(self.icon):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon = win32gui.LoadImage(
                hinst,
                self.icon,
                win32con.IMAGE_ICON,
                0,
                0,
                icon_flags
            )
        else:
            print("Can't find icon file - using default.")
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, (self.hwnd, 0, win32gui.NIF_INFO, win32con.WM_USER + 20, hicon, "Balloon Tooltip", message, 200, title))

    def _add_ids_to_menu_options(self, menu_options):
        result = []
        for menu_option in menu_options:
            option_text, option_icon, option_action = menu_option
            if callable(option_action) or option_action in self.SPECIAL_ACTIONS:
                self.menu_actions_by_id.add((self._next_action_id, option_action))
                result.append(menu_option + (self._next_action_id,))
            elif self.non_string_iterable(option_action):
                result.append((option_text, option_icon, self._add_ids_to_menu_options(option_action), self._next_action_id))
            else:
                print('Unknown item', option_text, option_icon, option_action)
            self._next_action_id += 1
        return result

    def refresh_icon(self):
        # Try and find a custom icon
        hinst = win32gui.GetModuleHandle(None)
        if os.path.isfile(self.icon):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon = win32gui.LoadImage(
                hinst,
                self.icon,
                win32con.IMAGE_ICON,
                0,
                0,
                icon_flags
            )
        else:
            print("Can't find icon file - using default.")
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        if self.notify_id: message = win32gui.NIM_MODIFY
        else: message = win32gui.NIM_ADD
        self.notify_id = (
            self.hwnd,
            0,
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            win32con.WM_USER + 20,
            hicon,
            self.hover_text
        )
        win32gui.Shell_NotifyIcon(message, self.notify_id)

    def restart(self, hwnd, msg, wparam, lparam):
        self.refresh_icon()

    def destroy(self, hwnd, msg, wparam, lparam):
        if self.on_quit: self.on_quit(self)
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32gui.PostQuitMessage(0) # Terminate the app.
        self._is_alive = False

    def notify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONDBLCLK:
            self.execute_menu_option(self.default_menu_index + self.FIRST_ID)
        elif lparam == win32con.WM_RBUTTONUP:
            self.show_menu()
        elif lparam == win32con.WM_LBUTTONUP:
            pass
        return True

    def show_menu(self):
        menu = win32gui.CreatePopupMenu()
        self.create_menu(menu, self.menu_options)
        #win32gui.SetMenuDefaultItem(menu, 1000, 0)

        pos = win32gui.GetCursorPos()
        # See http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winui/menus_0hdi.asp
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_LEFTALIGN,
            pos[0],
            pos[1],
            0,
            self.hwnd,
            None
        )
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

    def create_menu(self, menu, menu_options):
        for option_text, option_icon, option_action, option_id in menu_options[::-1]:
            if option_icon:
                option_icon = self.prep_menu_icon(option_icon)

            if option_id in self.menu_actions_by_id:                
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text, hbmpItem=option_icon, wID=option_id)
                win32gui.InsertMenuItem(menu, 0, 1, item)
            else:
                submenu = win32gui.CreatePopupMenu()
                self.create_menu(submenu, option_action)
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text, hbmpItem=option_icon, hSubMenu=submenu)
                win32gui.InsertMenuItem(menu, 0, 1, item)

    def prep_menu_icon(self, icon):
        # First load the icon.
        ico_x = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
        ico_y = win32api.GetSystemMetrics(win32con.SM_CYSMICON)
        hicon = win32gui.LoadImage(0, icon, win32con.IMAGE_ICON, ico_x, ico_y, win32con.LR_LOADFROMFILE)

        hdcBitmap = win32gui.CreateCompatibleDC(0)
        hdcScreen = win32gui.GetDC(0)
        hbm = win32gui.CreateCompatibleBitmap(hdcScreen, ico_x, ico_y)
        hbmOld = win32gui.SelectObject(hdcBitmap, hbm)
        # Fill the background.
        brush = win32gui.GetSysColorBrush(win32con.COLOR_MENU)
        win32gui.FillRect(hdcBitmap, (0, 0, 16, 16), brush)
        # unclear if brush needs to be feed.  Best clue I can find is:
        # "GetSysColorBrush returns a cached brush instead of allocating a new
        # one." - implies no DeleteObject
        # draw the icon
        win32gui.DrawIconEx(hdcBitmap, 0, 0, hicon, ico_x, ico_y, 0, 0, win32con.DI_NORMAL)
        win32gui.SelectObject(hdcBitmap, hbmOld)
        win32gui.DeleteDC(hdcBitmap)

        return hbm

    def command(self, hwnd, msg, wparam, lparam):
        id = win32gui.LOWORD(wparam)
        self.execute_menu_option(id)

    def execute_menu_option(self, id):
        menu_action = self.menu_actions_by_id[id]      
        if menu_action == self.QUIT:
            self._is_alive = False
        else:
            menu_action(self)

class MissingJob(Exception):
    """Raised when no job is found"""
    pass

class MissingOption(Exception):
    """Raised when an option is missing"""
    pass

class MissingSection(Exception):
    """Raised when an a section is missing"""
    pass

class Command(threading.Thread):
    def __init__(self, cmd, name):
        threading.Thread.__init__(self)
        self.name = name
        self.log_path = f"{LOG_PATH}/{name}.log"
        self.cmd = cmd
        self.quit = False
        self.finished = False

    def run(self):
        open(self.log_path, 'w').close()
        with open(self.log_path, 'a') as f:
            process = subprocess.Popen(
                self.cmd, 
                stdout = f,
                stderr = subprocess.STDOUT,
                universal_newlines = True
            )
            
            while process.poll() is None and not self.quit:
                time.sleep(1)
            self.finished = True

def parse_jobs(cfg):
    jobs = {}
    for job in [i for i in cfg.sections() if "JOB" in i]:
        jobs[job] = {
            "name": config[job]["NAME"],
            "path": os.path.expandvars(config[job]["PATH"]),
            "remote": config[job]["REMOTE"]
        }
    if not jobs:
        raise MissingJob("No jobs were found.")
    return jobs

def parse_cfg(section, cfg, env=None):
    if section not in cfg:
        raise MissingSection(f"Missing '{section}' section.")

    parsed = {}
    for key, val in cfg.items(section):
        if env:
            for _e, _v in env:
                val = val.replace(_e, _v)
        parsed[key] = val
    return parsed

def create_commands(jobs, arguments, parameters, options):
    cmds = {}
    cmd = "rclone"

    for opt in options.values():
        cmd += f" {opt}"
    
    for param, val in parameters.items():
        if (val == "1"):
            cmd += f" --{param}"

    for arg, val in arguments.items():
        cmd += f" --{arg} {val}"

    for job in jobs.values():
        job_cmd = f"{cmd} \"{job['path']}\" \"{job['remote']}\""

        cmds[job['name']] = job_cmd
    
    return cmds

config = configparser.ConfigParser(interpolation=None)

if not os.path.isfile(CONFIG_PATH):
    print("Config file not found. Creating a new one.")
    with open(CONFIG_PATH, "w") as f:
        f.write(CONFIG_TEMPLATE)

config.read(CONFIG_PATH)

if not os.path.isdir(LOG_PATH):
    os.mkdir(LOG_PATH)

try:
    env = parse_cfg("ENVIROMENT", config)
    jobs = parse_jobs(config)
    arguments = parse_cfg("ARGUMENTS", config)
    parameters = parse_cfg("PARAMETERS", config)
    options = parse_cfg("OPTIONS", config)
    
    if not options.get('mode'):
        raise MissingOption("mode", "Mode option is required for rclone to function.")
except Exception as e:
    print(e)
    sys.exit()

commands = create_commands(jobs, arguments, parameters, options)

processes = []
for name, command in commands.items():
    cmd = Command(command, name)
    cmd.start()
    processes.append(cmd)
process_count = len(processes) 

def tray_quit(tray):
    tray.create_notification(
        'rClone Backup Status', 
        f"Finished: {process_count - len(processes)}/{process_count} jobs"
    )
    print('Quitting.')

sys_tray = SysTray(TRAY_ICON, TRAY_TEXT, [], on_quit=tray_quit, default_menu_index=1, window_class_name="rClone Backup")
sys_tray.start()

processes_finished = False

while not processes_finished and sys_tray._is_alive:
    processes_finished = len(processes) == 0
    
    new_processes = processes
    for process in processes:
        if process.finished:
            new_processes.remove(process);
            continue
    print(f"Finished: {process_count - len(processes)}/{process_count} jobs")
    processes = new_processes
    time.sleep(1)

sys_tray._is_alive = False
if len(processes) > 0:
    for process in processes:
        process.quit = True
