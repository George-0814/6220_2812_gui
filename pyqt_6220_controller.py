from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from cs_6220_core_func import Keithley6220  # Import the core function class

ARM_CHECK_INTERVAL = 1000  # ✅ Interval for arming status check in ms
ARM_TIMEOUT = 20  # ✅ Timeout for arming in seconds

class Keithley6220Qt(Keithley6220, QObject):
    # Signal to notify the UI about connection status
    connected_signal = pyqtSignal(bool, str)  # ✅(True/False, message)
    error_signal = pyqtSignal(str) # ✅error signal
    nv_2182a_signal = pyqtSignal(str)  # ✅ New signal for 2182A presence
    params_set_signal = pyqtSignal(str, str)  # ✅(total_points, message)
    interlock_signal = pyqtSignal(bool)  # ✅Emits True (closed) or False (open)
    arm_status_signal = pyqtSignal(bool)  # ✅Emits True (armed) or False (unarmed)
    arming_timeout_signal = pyqtSignal()  # ✅Emits when arming times out
    arming_signal = pyqtSignal(bool, str)  # ✅Emits (True = success, False = failure), with a message
    abort_signal = pyqtSignal(bool, str)  # ✅ Emits (True = success, False = failure), with a message
    inner_shield_signal = pyqtSignal(str)  # ✅ Emits the inner shield status ("GUARD" or "OLOW")
    inner_shield_error_signal = pyqtSignal(str)  # ✅ Emits error messages for inner shield
    output_state_signal = pyqtSignal(str)  # ✅ Emits "ON" or "OFF"
    output_state_error_signal = pyqtSignal(str)  # ✅ Emits an error message if query fails
    measurement_signal = pyqtSignal(bool, str)  # ✅ Emits (True = success, False = failure), with a message
    iv_data_ready_signal = pyqtSignal()  # ✅ Emits when data is ready


    def __init__(self, address, parent=None):
        """Initialize Keithley6220 and integrate with PyQt."""
        QObject.__init__(self, parent)  # Initialize QObject
        Keithley6220.__init__(self, address)  # Initialize Keithley core functions
        # timer parameters for arming monitoring
        self.elapsed_time = 0  # Track time for timeout logic
        self.arming_timeout = 20  # ✅ Timeout for arming in seconds
        self.interval = 1000  # ✅ Check every 1 second (1000 ms)
        # ✅ Timer for periodic status checking
        self.arm_timer = QTimer()
        self.arm_timer.timeout.connect(self._check_arming_progress)
        # self instance for storing readings to be used in the GUI
        self.current_values = []  # ✅ Store ADC values
        self.voltage_values = []  # ✅ Store VDC values


    def connect_device(self):
        """Connect to the Keithley 6220, enable all data output, check 2182A and emit signals."""
        print("try Keithley 6220 connected.")
        response = super().connect()  # Call the existing `connect()` method
        if "Error" in response:
            self.connected_signal.emit(False, response) # Emit failure signal
            return
        else:
            # ✅ Emit success signal
            self.connected_signal.emit(True, response)
            # enable all data output
            data_type_set = super().enable_all_data_output()
            if data_type_set:
                print("All data output enabled.")
            else:
                self.error_signal.emit("Failed to enable all data output.")
            # ✅ Check for 2182A and emit presence status
            is_present = self.check_2182a_presence()
            if is_present:
                self.nv_2182a_signal.emit("Connected")
            else:
                self.nv_2182a_signal.emit("Not detected.")

    def disconnect_device(self):
        """Disconnect from the Keithley 6220 and emit signal."""
        super().disconnect()  # ✅ Calls the core function, which already checks connection
        self.connected_signal.emit(False, "Disconnected")  # Notify UI

    def check_err_message(self):
        """Calls the core function and emits any error found."""
        result = super().check_error_message()  # Call the existing function

        if isinstance(result, tuple):  # If an error exists, emit it as a signal
            error_code, error_message = result
            self.error_signal.emit(f"Error {error_code}: {error_message}")
        elif result == None:
            self.error_signal.emit("No error.")
        else:
            self.error_signal.emit(f"{result}")

    def set_diff_cond_params(self, start, stop, step, delay=0.002, delta=1e-5):
        """Calls the core function and emits success or error messages."""
        total_points, result = super().set_differential_conductance_params(start, stop, step, delay, delta)

        if total_points is None:  # ✅ Error case (result contains the error message)
            self.error_signal.emit(result)
        else:  # ✅ Success case
            self.params_set_signal.emit(total_points, result)  # Emit success signal

    def check_interlock(self):
        """Calls the core check interlock function and emits the interlock status."""

        is_closed = super().check_interlock_status()  # ✅ Call the existing function
        if is_closed:  # If interlock is closed, emit True
            self.interlock_signal.emit(True)  # ✅ Emit interlock status
        elif not is_closed :  # Return for further use if needed
            self.interlock_signal.emit(False)
        else:
            self.error_signal.emit("Error in interlock status.")

    def check_arm(self):
        """Calls the core function and emits the arming status."""
        try:
            is_armed = super().check_arm_status()  # ✅ Call the existing function
            if is_armed is not None:
                self.arm_status_signal.emit(is_armed)  # ✅ Emit arming status
                self.is_armed = is_armed  # ✅ Update flag
                return is_armed  # Return for further use if needed
            else:
                self.error_signal.emit("Unexpected arming status response.")  # Handle unexpected cases
                return is_armed
        except Exception as e:
            self.error_signal.emit(f"Error: {e}.")


    def start_arming_monitor(self):
        """Starts monitoring the arming status every second until timeout."""
        self.elapsed_time = 0
        self.arm_timer.start(self.interval)  # ✅ Start QTimer with interval

    def stop_arming_monitor(self):
        """Stops the arming monitor timer."""
        self.arm_timer.stop()
        self.under_arming = False  # ✅ Reset flag
        print("Arming monitor stopped. Flag reset.")

    def arm_device(self):
        """Arms the 6220 and monitor arming process of the device with a QT timer constantly check."""
        try:
            if self.under_arming:  # ✅ Prevents multiple arm commands while waiting
                self.arming_signal.emit(False, "Arming already in progress.")
                return

            success = super().arm_device()  # ✅ Call the core function

            if success:
                self.under_arming = True  # ✅ Set flag to prevent duplicate commands
                self.arming_signal.emit(True, "Arming process initiated.")
                self.monitor_arming_status()  # ✅ Start monitoring with QTimer
            else:
                self.arming_signal.emit(False, "Failed to arm the device. Check preconditions.")

        except Exception as e:
            self.under_arming = False  # ✅ Ensure flag resets on error
            self.error_signal.emit(f"Error during arming: {e}")

    def monitor_arming_status(self, timeout=ARM_TIMEOUT, interval=ARM_CHECK_INTERVAL):
        """Monitors arming status and ensures the user cannot send another command prematurely."""
        self.elapsed_time = 0  # Reset elapsed time
        self.arming_timeout = timeout
        self.arm_timer.start(interval)

    def _check_arming_progress(self):
        """Helper function for monitoring arming status."""
        is_armed = self.check_arm_status()  # ✅ Reuses existing function

        if is_armed:
            print("Device armed successfully. Ready to start the test.")
            self.arming_signal.emit(True, "Device successfully armed.")
            self.arm_status_signal.emit(True)  # ✅ Emit arming status
            self.under_arming = False  # ✅ Allow user to initiate new commands
            self.is_armed = True  # ✅ Update flag
            self.arm_timer.stop()  # ✅ Stop monitoring

        else:
            self.elapsed_time += ARM_CHECK_INTERVAL/1000  # Track time in seconds
            if self.elapsed_time >= self.arming_timeout:
                print("Arming process timed out.")
                self.arming_signal.emit(False, "Arming process timed out.")
                self.under_arming = False  # ✅ Reset flag on timeout
                self.arm_timer.stop()

    def abort_process(self):
        """Aborts the process only if the device is armed or undergoing measurement."""
        try:
            if not self.is_armed:
                self.abort_signal.emit(False, "Abort not needed: Device is not armed.")
                return False

            # Send the abort command
            success = super().abort_process()

            if success:
                self.arm_timer.stop()  # ✅ Stop the arming monitor
                self.abort_signal.emit(True, "Process aborted successfully.")
                self.is_armed = False  # ✅ Reset armed status
            else:
                self.abort_signal.emit(False, "Failed to abort process.")

        except Exception as e:
            self.error_signal.emit(f"Error aborting process: {e}")
            return False

    def query_inner_shield(self):
        """Queries the inner shield setting, updates attribute, and emits signal."""
        try:
            shield_status = super().query_inner_shield()  # ✅ Call the core function

            if shield_status is not None:
                self.inner_shield_status = shield_status  # ✅ Update attribute
                self.inner_shield_signal.emit(shield_status)  # ✅ Emit status to UI

            return shield_status

        except Exception as e:
            self.error_signal.emit(f"Error querying inner shield: {e}")  # ✅ Emit error signal
            return None

    def set_inner_shield_to_guard(self):
        """Calls the core function and emits signals for success or failure."""
        try:
            result = super().set_inner_shield_to_guard()  # ✅ Call the core function

            if result == True:
                self.inner_shield_signal.emit("GUARD")  # ✅ Successfully changed
            elif result == "OUTPUT_ON":
                self.error_signal.emit("Cannot change inner shield: Output is ON.")  # ✅ Blocked action
            elif result == False:
                self.error_signal.emit("Warning: Inner shield setting not confirmed.")
            else:
                self.error_signal.emit("Error setting inner shield.")  # ✅ Handles None (exception case)

        except Exception as e:
            self.error_signal.emit(f"Error setting inner shield: {e}")

    def update_output_state(self):
        """Queries output state, updates attribute, and emits signal."""
        try:
            state = super().update_output_state()  # ✅ Call the core function

            if state is not None:
                self.output_state = state  # ✅ Update attribute
                self.output_state_signal.emit(state)  # ✅ Emit signal to UI
            else:
                self.error_signal.emit("Error: Failed to retrieve output state.")  # ✅ Emit error signal

            return state

        except Exception as e:
            self.error_signal.emit(f"Error querying output state: {e}")  # ✅ Emit error signal
            return None

    def update_inner_shield_status(self):
        """Queries inner shield status, updates attribute, and emits signal."""
        try:
            shield_status = super().update_inner_shield_status()  # ✅ Call the core function

            if shield_status is not None:
                self.inner_shield_status = shield_status  # ✅ Update attribute
                self.inner_shield_signal.emit(shield_status)  # ✅ Emit signal to UI
            else:
                self.inner_shield_error_signal.emit(
                    "Error: Failed to retrieve inner shield status.")  # ✅ Emit error signal

            return shield_status

        except Exception as e:
            self.error_signal.emit(f"Error querying inner shield: {e}")  # ✅ Emit error signal
            return None

    def initialize_differential_conductance(self):
        """Starts the Differential Conductance measurement and emits signals for UI updates."""
        try:
            print("Initializing Differential Conductance Measurement...")

            # ✅ Use stored `self.is_armed` instead of querying again
            if not self.is_armed:
                self.measurement_signal.emit(False, "Device is not armed. Run 'Arm Device' first.")
                return False

            # ✅ Call the core function to start measurement
            success = super().initialize_differential_conductance()

            if success:
                self.measurement_signal.emit(True, "Differential Conductance Measurement Started.")
            else:
                self.measurement_signal.emit(False, "Failed to start measurement.")

            return success

        except Exception as e:
            self.error_signal.emit(False, f"Error initializing measurement: {e}")
            return False

    def retrieve_iv_data(self):
        """Retrieves stored I-V data from the device buffer and updates self."""
        try:
            raw_data = self.get_all_differential_conductance_data()
            if not raw_data:
                self.error_signal.emit("Failed to retrieve measurement data.")
                return
            # ✅ Parse and store in self
            self.current_values, self.voltage_values = super().parse_iv_data(raw_data)
            # check if data is parsed successfully
            if len(self.current_values) == 0 or len(self.voltage_values) == 0:
                self.error_signal.emit("Failed to parse measurement data.")
                return
            # ✅ Emit a signal to notify the UI that data is ready
            self.iv_data_ready_signal.emit()
        except Exception as e:
            self.error_signal.emit(f"Error retrieving I-V data: {e}")