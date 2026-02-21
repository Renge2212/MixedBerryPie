import os
import sys

# Ensure the root directory is in the python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if __name__ == "__main__":
    import traceback

    # Initialize basic logging first
    try:
        from src.core.logger import get_logger, setup_logger

        setup_logger()  # Ensure 'piemenu' logger exists with handlers
        logger = get_logger("launcher")
        logger.info("Starting MixedBerryPie via launcher")
    except Exception as e:
        print(f"FAILED TO INITIALIZE LOGGER: {e}")
        traceback.print_exc()
        sys.exit(1)

    try:
        # Import App inside the try block to catch import errors
        from src.app import MixedBerryPieApp

        menu = MixedBerryPieApp()
        menu.run()
    except Exception as e:
        error_msg = f"Launcher: Application failed to start: {e}"
        logger.critical(error_msg, exc_info=True)
        # Fallback print to ensure it's visible if logging is silent/to-file-only
        print(f"\nCRITICAL ERROR: {error_msg}")
        traceback.print_exc()
        sys.exit(1)
