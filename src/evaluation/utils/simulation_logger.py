import sys
import os


class SimulationLogger:
    """
    Logger for simulation runs, logs both on console and to a file, centralizing the logging.
    """

    _original_stdout = sys.stdout

    def __init__(self, log_filename: str):
        """
        Initialize the logger and open the log file, given the full path
        """
        self.log_file_path = log_filename
        self.log_file = None

        log_dir = os.path.dirname(log_filename)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        try:
            self.log_file = open(log_filename, 'w', buffering=1)
            self.log(f"--- Log file initialized at: {log_filename} ---")
        except Exception as e:
            self._original_stdout.write(f"CRITICAL: Cannot open log file {log_filename}: {e}\n")

    def log(self, message: str):
        """Log message to both console and log file"""
        self._original_stdout.write(message + "\n")
        if self.log_file:
            try:
                self.log_file.write(message + "\n")
            except Exception as e:
                self._original_stdout.write(f"CRITICAL: Failed to write to log file: {e}\n")

    def flush(self):
        """Flush the log file buffer."""
        if self.log_file:
            self.log_file.flush()

    def close(self):
        """Flush and close the log file"""
        if self.log_file:
            try:
                self.log(f"--- Closing log file: {self.log_file_path} ---")
                self.log_file.close()
            except Exception as e:
                self._original_stdout.write(f"Failed to close log file: {e}\n")
            finally:
                self.log_file = None #set the file to None anyway
