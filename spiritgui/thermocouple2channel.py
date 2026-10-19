import threading
import time
import nidaqmx
from nidaqmx.constants import (
    ThermocoupleType,
    CJCSource,
    ADCTimingMode,
    AcquisitionType,
)
from spiritgui import SpiritGui

DEVICE_CHANNELS = "cDAQ1Mod1/ai0, cDAQ1Mod1/ai1"  # ai0 and ai1
CHANNEL_LABELS = ["ai0", "ai1"]
PHYSICAL_CHANNELS = [name.strip() for name in DEVICE_CHANNELS.split(",")]
SAMPLE_RATE = 10.0
TOTAL_SECONDS = 30


def acquire(on_sample):
    """Read both thermocouples for TOTAL_SECONDS, calling on_sample(physical_channel, temperature) per reading."""
    with nidaqmx.Task() as task:
        channels = task.ai_channels.add_ai_thrmcpl_chan(
            DEVICE_CHANNELS,
            thermocouple_type=ThermocoupleType.T,
            cjc_source=CJCSource.BUILT_IN,
        )

        # Faster conversion, with less filtering/noise rejection.
        # Applies to both channels (the NI-9213 shares one ADC across channels).
        channels.ai_adc_timing_mode = ADCTimingMode.HIGH_SPEED

        # Configure actual hardware-timed sampling.
        task.timing.cfg_samp_clk_timing(
            rate=SAMPLE_RATE,
            sample_mode=AcquisitionType.CONTINUOUS,
            samps_per_chan=10,
        )

        print(f"Starting acquisition at {SAMPLE_RATE} samples/second...")
        task.start()
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < TOTAL_SECONDS:
            # No time.sleep(): this blocks until the next hardware sample.
            # With two channels, read() returns [[ai0_value], [ai1_value]].
            sample = task.read(
                number_of_samples_per_channel=1,
                timeout=2.0,
            )
            readings = [channel_data[0] for channel_data in sample]

            elapsed = time.perf_counter() - start_time
            for physical_channel, temperature in zip(PHYSICAL_CHANNELS, readings):
                on_sample(physical_channel, temperature)

            print(
                f"Time: {elapsed:.1f}s | "
                + " | ".join(
                    f"{label}: {temperature:.2f} °C"
                    for label, temperature in zip(CHANNEL_LABELS, readings)
                )
            )
    print("Acquisition finished.")


if __name__ == "__main__":
    gui = SpiritGui()
    for label, physical_channel in zip(CHANNEL_LABELS, PHYSICAL_CHANNELS):
        gui.add_ai_channel("°C", label, physical_channel)

    threading.Thread(target=acquire, args=(gui.update_ai_value,), daemon=True).start()
    gui.start()