import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from iv_curve_measure import Ui_MainWindow  # Import the generated UI class
from pyqt_6220_controller import Keithley6220Qt  # Import Keithley controller
from PyQt6.QtCore import QObject, pyqtSignal
from datetime import datetime
import pyqtgraph as pg

class QTextBrowserStream(QObject):
    """Redirects stdout to QTextBrowser."""
    new_text = pyqtSignal(str)  # Define a signal

    def write(self, text):
        """Emit new text to be displayed."""
        self.new_text.emit(text)

    def flush(self):
        """Required for compatibility, but not needed."""
        pass

class IVMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # Setup the UI

        # Initialize Keithley Controller
        self.keithley_controller = Keithley6220Qt("GPIB0::12::INSTR")  # Adjust address
        # todo: how the signal is emit into a function as params?
        # Connect Signals to UI Updates
        self.keithley_controller.connected_signal.connect(self.update_keithley_status_by_bool)
        self.keithley_controller.error_signal.connect(self.display_error)
        self.keithley_controller.nv_2182a_signal.connect(self.update_2182a_status)
        self.keithley_controller.arm_status_signal.connect(self.update_arm_status)
        self.keithley_controller.output_state_signal.connect(self.update_output_status)
        self.keithley_controller.measurement_signal.connect(self.update_keithley_status_by_bool)
        self.keithley_controller.inner_shield_signal.connect(self.update_inner_shield_status)
        self.keithley_controller.params_set_signal.connect(self.update_param_labels)
        self.keithley_controller.arming_signal.connect(self.update_keithley_status_by_bool)
        self.keithley_controller.abort_signal.connect(self.update_keithley_status_by_bool)
        self.keithley_controller.interlock_signal.connect(self.update_interlock_status)
        self.keithley_controller.iv_data_ready_signal.connect(self.update_iv_plot)


        # Connect Menu Actions
        self.actionKeithley6220.triggered.connect(self.connect_keithley)
        self.actionKeithley6220_discon.triggered.connect(self.disconnect_keithley)
        self.actionArm_device.triggered.connect(self.arm_device)
        self.actionStart_i_v_measure.triggered.connect(self.start_iv_measure)
        self.actionStop_i_v_measure.triggered.connect(self.abort_process)
        self.actionArmed.triggered.connect(self.armed_query)
        self.actionOUTPUT_status.triggered.connect(self.query_output_status)
        self.actionError_message.triggered.connect(self.check_error_message)
        self.actionVerify_params.triggered.connect(self.verify_params)
        self.actionInterlock.triggered.connect(self.check_interlock)
        self.actionRetrieve_Data.triggered.connect(self.retrieve_iv_data)
        self.actionStop_arm_query_timer.triggered.connect(self.stop_arm_timer)
        self.actionInit_measurement.triggered.connect(self.init_measurement)

        # Initialize the output redirection (print function display)
        self.output_stream = QTextBrowserStream()
        self.output_stream.new_text.connect(self.append_output)  # Connect signal to slot
        sys.stdout = self.output_stream  # Redirect stdout to QTextBrowserStream


        # Initialize the plot
        self.plot = self.ui_plot_canva
        self.plot.setBackground("w")  # ✅ White background
        self.plot.setLabel("left", "Voltage (V)")
        self.plot.setLabel("bottom", "Current (A)")
        self.plot.addLegend()
        # Add curve for real-time updates
        self.curve = self.plot.plot([], [], pen=pg.mkPen(color="b", width=2), name="I-V Curve")

    def append_output(self, text):
        """Appends redirected stdout text to status box."""
        if text.strip():  # Avoid adding empty lines
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.console_statusbox.append(f"[{timestamp}] {text.strip()}")

    def closeEvent(self, event):
        """Restore stdout when closing the application."""
        sys.stdout = sys.__stdout__
        event.accept()

    def connect_keithley(self):
        """Handles device connection."""
        self.log_message("Connection initiating.")
        self.keithley_controller.connect_device()

    def log_message(self, message):
        """Helper function to log messages with a timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.keithley6220_statusbox.append(f"[{timestamp}] {message}")

    def disconnect_keithley(self):
        """Handles device disconnection."""
        self.log_message("Disconnecting.")
        self.keithley_controller.disconnect_device()

    def update_keithley_status_by_bool(self, success, message):

        """Updates the Keithley 6220 status box with a timestamp."""
        if success:
            self.log_message(f"Success: {message}")
        else:
            self.log_message(f"Error: {message}")

    def update_2182a_status(self, message):
        """Updates the Keithley 2182A status label."""
        self.nv_2182a_label.setText(message)

    def update_inner_shield_status(self, status):
        """Updates the Inner Shield Status label."""
        self.log_message(f"Inner shield status is {status}.")
        self.inner_shield_label.setText(status)

    def update_arm_status(self, armed):
        """Updates the Arm Status label."""
        status = "Armed" if armed else "Not Armed"
        self.log_message(f"Armed status is {status}.")
        self.arm_status_label.setText(status)

    def update_output_status(self, status):
        """Updates the Output Status label."""
        self.log_message(f"The output status is: {status}.")
        self.output_status_label.setText(status)

    def display_error(self, message):
        """Displays error messages."""
        self.keithley6220_statusbox.setText(f"Error: {message}")
        self.log_message(f"Error: {message}")

    def arm_device(self):
        """Set the params for measurment and arm the Keithley device."""
        self.log_message("Arming device.")
        try:
            start_current = float(self.start_cur_inputbox.toPlainText())
            stop_current = float(self.stop_cur_inputbox.toPlainText())
            step_size = float(self.cur_step_inputbox.toPlainText())
            delay = float(self.delay_inputbox.toPlainText()) if self.delay_inputbox.toPlainText() else 0.002
            delta = float(self.delta_inputbox.toPlainText()) if self.delta_inputbox.toPlainText() else 1e-5

            # Set measurement parameters
            self.keithley_controller.set_diff_cond_params(start_current, stop_current, step_size, delay, delta)
            self.keithley_controller.arm_device()

        except ValueError:
            self.display_error("Invalid input values!")

    def start_iv_measure(self):
        """Starts IV measurement using the given parameters from UI."""
        self.log_message("Start measurment. (temporary removed)")
        # try:
        #     start_current = float(self.start_cur_inputbox.toPlainText())
        #     stop_current = float(self.stop_cur_inputbox.toPlainText())
        #     step_size = float(self.cur_step_inputbox.toPlainText())
        #     delay = float(self.delay_inputbox.toPlainText()) if self.delay_inputbox.toPlainText() else 0.002
        #     delta = float(self.delta_inputbox.toPlainText()) if self.delta_inputbox.toPlainText() else 1e-5
        #
        #     # Set measurement parameters
        #     self.keithley_controller.set_diff_cond_params(start_current, stop_current, step_size, delay, delta)
        #     self.keithley_controller.initialize_differential_conductance()
        #
        # except ValueError:
        #     self.display_error("Invalid input values!")

    def abort_process(self):
        """Aborts the measurement process."""
        self.log_message("Abort initiate.")
        self.keithley_controller.abort_process()

    def armed_query(self):
        """Query arm status."""
        self.log_message("Armed query sent.")
        self.keithley_controller.check_arm()
        
    def query_inner_shield(self):
        """Query the inner shield status."""
        self.log_message("Inner shield config query sent.")
        self.keithley_controller.query_inner_shield()
        pass

    def query_output_status(self):
        """Query the output status."""
        self.log_message("Output status query sent.")
        self.keithley_controller.update_output_state()

    def init_measurement(self):
        """Initialize the measurement."""
        self.log_message("Measurement initiated.")
        self.keithley_controller.initialize_differential_conductance()

    def check_error_message(self):
        """Check for error messages."""
        self.log_message("Error message query sent.")
        self.keithley_controller.check_err_message()

    # --------------2/6-------------

    def verify_params(self):
        """Read inputs and set params to 6220 then verify params are correctly set."""
        self.log_message("Verifying parameters.")
        try:
            start_current = float(self.start_cur_inputbox.toPlainText())
            stop_current = float(self.stop_cur_inputbox.toPlainText())
            step_size = float(self.cur_step_inputbox.toPlainText())
            delay = float(self.delay_inputbox.toPlainText()) if self.delay_inputbox.toPlainText() else 0.002
            delta = float(self.delta_inputbox.toPlainText()) if self.delta_inputbox.toPlainText() else 1e-5

            # Set measurement parameters
            self.keithley_controller.set_diff_cond_params(start_current, stop_current, step_size, delay, delta)
            self.keithley_controller.verify_params()
        except ValueError:
            self.display_error("Invalid input values!")

    def update_param_labels(self, total_points, estimated_time):
        """Update differential conductance parameters, total points and estimated time in ui label."""
        self.log_message("Parameters updated.")
        self.start_current_lab.setText(str(self.keithley_controller.start))
        self.stop_current_lab.setText(str(self.keithley_controller.stop))
        self.current_step_lab.setText(str(self.keithley_controller.step))
        self.delay_label.setText(str(self.keithley_controller.delay))
        self.delta_label.setText(str(self.keithley_controller.delta))
        self.remain_time_label.setText(str(estimated_time))
        self.totalpoint_label.setText(str(total_points))

    def set_inner_shield_to_guard(self):
        self.log_message("Setting inner shield to GUARD.")
        self.keithley_controller.set_inner_shield_to_guard()

    def check_interlock(self):
        self.log_message("Query interlock status")
        self.keithley_controller.check_interlock()

    def update_interlock_status(self, status):
        if status:
            self.interlock_label.setText("LOCKED")
        else:
            self.interlock_label.setText("OPEN")

    def update_iv_plot(self):
        """Plots the stored I-V data using PyQtGraph."""
        self.log_message("Plotting I-V data.")
        # Update the plot with the new data
        self.curve.setData(self.keithley_controller.current_values,
                           self.keithley_controller.voltage_values)

    def retrieve_iv_data(self):
        """Retrieve the I-V data from the Keithley device."""
        self.log_message("Retrieving I-V data.")
        self.keithley_controller.retrieve_iv_data()

    def stop_arm_timer(self):
        """Special function for stopping the arming timer. """
        self.log_message("Stop arm timer.")
        self.keithley_controller.stop_arming_monitor()




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IVMainWindow()
    window.show()
    sys.exit(app.exec())
