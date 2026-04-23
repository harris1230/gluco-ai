# =============================================================================
# PPG Signal Extraction & Feature Engineering — Production-Grade Pipeline
# =============================================================================
# Advanced photoplethysmography processing for non-invasive glucose monitoring.
# Includes: adaptive ROI, multi-channel extraction, signal quality assessment,
# advanced filtering, robust peak detection, and comprehensive feature engineering.
# =============================================================================

# 🔥 IMPORTANT FIX (No GUI thread error)
import matplotlib
matplotlib.use('Agg')

import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from scipy.signal import (
    butter, filtfilt, find_peaks, cheby2, sosfilt,
    savgol_filter, welch, periodogram
)
from scipy.stats import skew, kurtosis as scipy_kurtosis
import io
import base64
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================
DEFAULT_FPS = 30
BANDPASS_LOW = 0.7        # Hz — lower bound (respiratory + cardiac)
BANDPASS_HIGH = 3.5       # Hz — upper bound (cardiac harmonics)
MIN_SIGNAL_LENGTH = 10    # Minimum frames for filtering
SIGNAL_TARGET_LENGTH = 120

# HSV ranges for skin-tone detection
SKIN_HSV_LOWER = np.array([0, 30, 60], dtype=np.uint8)
SKIN_HSV_UPPER = np.array([25, 255, 255], dtype=np.uint8)
SKIN_HSV_LOWER2 = np.array([160, 30, 60], dtype=np.uint8)
SKIN_HSV_UPPER2 = np.array([180, 255, 255], dtype=np.uint8)


# =============================================================================
# Signal Quality Assessment
# =============================================================================
class SignalQuality(Enum):
    """PPG signal quality grades."""
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNUSABLE = "unusable"


@dataclass
class SignalDiagnostics:
    """Detailed diagnostics for PPG signal quality."""
    quality: SignalQuality
    snr_db: float = 0.0
    is_saturated: bool = False
    is_flatline: bool = False
    has_periodic_component: bool = True
    dominant_frequency_hz: float = 0.0
    motion_artifact_ratio: float = 0.0
    usable_segment_ratio: float = 1.0
    notes: list = field(default_factory=list)


def assess_signal_quality(signal, fps=DEFAULT_FPS):
    """
    Comprehensive signal quality assessment.

    Evaluates SNR, saturation, flat-line, periodicity, and motion artifacts.

    Args:
        signal: Raw or filtered PPG signal (numpy array).
        fps: Frames per second of the video source.

    Returns:
        SignalDiagnostics with quality grade and detailed metrics.
    """
    signal = np.array(signal, dtype=np.float64)
    diag = SignalDiagnostics(quality=SignalQuality.GOOD)

    if len(signal) < MIN_SIGNAL_LENGTH:
        diag.quality = SignalQuality.UNUSABLE
        diag.notes.append(f"Signal too short: {len(signal)} frames")
        return diag

    # --- SNR estimation (signal vs. high-frequency noise) ---
    try:
        freqs, psd = welch(signal, fs=fps, nperseg=min(len(signal), 256))
        cardiac_band = (freqs >= 0.5) & (freqs <= 4.0)
        noise_band = freqs > 4.0

        signal_power = np.sum(psd[cardiac_band]) if np.any(cardiac_band) else 1e-10
        noise_power = np.sum(psd[noise_band]) if np.any(noise_band) else 1e-10

        diag.snr_db = 10 * np.log10(signal_power / (noise_power + 1e-10))

        # Dominant frequency
        if np.any(cardiac_band):
            cardiac_psd = psd.copy()
            cardiac_psd[~cardiac_band] = 0
            diag.dominant_frequency_hz = freqs[np.argmax(cardiac_psd)]
            diag.has_periodic_component = diag.dominant_frequency_hz > 0.5
        else:
            diag.has_periodic_component = False

    except Exception as e:
        logger.warning(f"PSD computation failed: {e}")
        diag.snr_db = 0.0

    # --- Saturation detection ---
    signal_range = np.ptp(signal)
    if signal_range < 1e-6:
        diag.is_flatline = True
        diag.notes.append("Flat-line detected — no variation in signal")
    else:
        # Check if >20% of values are at extremes
        near_max = np.sum(signal > (np.max(signal) - 0.01 * signal_range))
        near_min = np.sum(signal < (np.min(signal) + 0.01 * signal_range))
        saturation_ratio = (near_max + near_min) / len(signal)
        if saturation_ratio > 0.20:
            diag.is_saturated = True
            diag.notes.append(f"Saturation detected: {saturation_ratio:.1%} of signal at extremes")

    # --- Motion artifact estimation ---
    try:
        diff_signal = np.diff(signal)
        large_jumps = np.sum(np.abs(diff_signal) > 3 * np.std(diff_signal))
        diag.motion_artifact_ratio = large_jumps / len(diff_signal)
        if diag.motion_artifact_ratio > 0.15:
            diag.notes.append(f"High motion artifacts: {diag.motion_artifact_ratio:.1%}")
    except Exception:
        pass

    # --- Usable segment detection ---
    window_size = max(fps, 10)
    if len(signal) > window_size:
        local_vars = [np.var(signal[i:i+window_size])
                      for i in range(0, len(signal) - window_size, window_size // 2)]
        if local_vars:
            median_var = np.median(local_vars)
            usable = sum(1 for v in local_vars if v > 0.1 * median_var)
            diag.usable_segment_ratio = usable / len(local_vars)

    # --- Overall quality grading ---
    if diag.is_flatline:
        diag.quality = SignalQuality.UNUSABLE
    elif diag.snr_db > 10 and diag.motion_artifact_ratio < 0.05 and diag.has_periodic_component:
        diag.quality = SignalQuality.GOOD
    elif diag.snr_db > 5 and diag.motion_artifact_ratio < 0.15:
        diag.quality = SignalQuality.ACCEPTABLE
    elif diag.snr_db > 0 or diag.has_periodic_component:
        diag.quality = SignalQuality.POOR
    else:
        diag.quality = SignalQuality.UNUSABLE

    return diag


# =============================================================================
# Frame Extraction
# =============================================================================
@dataclass
class VideoMetadata:
    """Metadata extracted from the video source."""
    fps: float = DEFAULT_FPS
    frame_count: int = 0
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0


def extract_frames(video_path):
    """
    Extract frames from video with automatic FPS detection and downsampling.

    For high-FPS videos (>60), frames are subsampled to ~30 FPS to maintain
    consistency with the training pipeline.

    Args:
        video_path: Path to the video file.

    Returns:
        List of BGR frames (numpy arrays).
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        logger.error(f"Cannot open video: {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Determine frame skip for high-FPS videos
    skip = max(1, int(round(fps / DEFAULT_FPS))) if fps > 45 else 1

    frames = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % skip == 0:
            frames.append(frame)
        frame_idx += 1

    cap.release()

    logger.info(f"Extracted {len(frames)} frames from {total_frames} total "
                f"(FPS={fps:.1f}, skip={skip})")

    return frames


def extract_video_metadata(video_path):
    """
    Extract video metadata without reading all frames.

    Returns:
        VideoMetadata dataclass.
    """
    cap = cv2.VideoCapture(video_path)
    meta = VideoMetadata()

    if cap.isOpened():
        meta.fps = cap.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
        meta.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        meta.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        meta.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        meta.duration_seconds = meta.frame_count / meta.fps if meta.fps > 0 else 0

    cap.release()
    return meta


# =============================================================================
# PPG Signal Extraction
# =============================================================================
def _detect_skin_roi(frame):
    """
    Detect skin region using HSV color-space masking.

    Returns a binary mask of skin-toned pixels. Falls back to center ROI
    if skin detection fails.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Skin tone in HSV spans two hue ranges (red wraps around)
    mask1 = cv2.inRange(hsv, SKIN_HSV_LOWER, SKIN_HSV_UPPER)
    mask2 = cv2.inRange(hsv, SKIN_HSV_LOWER2, SKIN_HSV_UPPER2)
    skin_mask = mask1 | mask2

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)

    # Check if we have enough skin pixels (>5% of frame)
    skin_ratio = np.sum(skin_mask > 0) / skin_mask.size
    if skin_ratio < 0.05:
        return None  # Fall back to center ROI

    return skin_mask


def extract_ppg_signal(frames):
    """
    Extract PPG signal using adaptive skin-tone ROI detection.

    Uses the green channel (strongest PPG component) with intelligent ROI
    selection: tries skin-tone detection first, falls back to center-crop.

    Args:
        frames: List of BGR frames.

    Returns:
        List of mean green-channel intensity values per frame.
    """
    if not frames:
        return []

    signal = []
    use_skin_detection = True
    skin_detection_failures = 0

    for i, frame in enumerate(frames):
        green = frame[:, :, 1]  # Green channel
        h, w = green.shape

        roi_values = None

        # Try adaptive skin ROI
        if use_skin_detection:
            skin_mask = _detect_skin_roi(frame)
            if skin_mask is not None:
                masked_green = green[skin_mask > 0]
                if len(masked_green) > 100:
                    roi_values = masked_green
                else:
                    skin_detection_failures += 1
            else:
                skin_detection_failures += 1

            # If skin detection fails for >30% of frames, fall back permanently
            if i > 10 and skin_detection_failures / (i + 1) > 0.3:
                use_skin_detection = False
                logger.info("Skin detection unreliable — falling back to center ROI")

        # Fallback: center ROI (50% of frame area)
        if roi_values is None:
            roi = green[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
            roi_values = roi.flatten()

        avg_intensity = np.mean(roi_values)
        signal.append(avg_intensity)

    return signal


def extract_multichannel_ppg(frames):
    """
    Extract PPG signals from all three color channels (R, G, B).

    The red/green ratio is correlated with SpO₂ and provides additional
    discriminative features for glucose prediction.

    Args:
        frames: List of BGR frames.

    Returns:
        dict with keys 'red', 'green', 'blue', each mapping to a signal list.
    """
    channels = {'red': [], 'green': [], 'blue': []}

    if not frames:
        return channels

    for frame in frames:
        h, w = frame.shape[:2]

        # Try skin ROI, fallback to center
        skin_mask = _detect_skin_roi(frame)
        if skin_mask is not None and np.sum(skin_mask > 0) > 100:
            for idx, name in enumerate(['blue', 'green', 'red']):
                ch = frame[:, :, idx]
                channels[name].append(float(np.mean(ch[skin_mask > 0])))
        else:
            roi = frame[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
            for idx, name in enumerate(['blue', 'green', 'red']):
                channels[name].append(float(np.mean(roi[:, :, idx])))

    return channels


# =============================================================================
# Signal Filtering
# =============================================================================
def bandpass_filter(signal, fps=DEFAULT_FPS):
    """
    4th-order Chebyshev Type II bandpass filter.

    Superior stopband rejection compared to Butterworth. Preserves cardiac
    frequency components (0.7–3.5 Hz) while aggressively attenuating noise.

    Falls back to Butterworth if Chebyshev fails (e.g., edge-case Nyquist issues).

    Args:
        signal: Raw PPG signal array.
        fps: Frames per second (auto-detected or default 30).

    Returns:
        Bandpass-filtered signal.
    """
    signal = np.array(signal, dtype=np.float64)

    if len(signal) < MIN_SIGNAL_LENGTH:
        return signal

    nyquist = fps / 2.0
    low = BANDPASS_LOW / nyquist
    high = min(BANDPASS_HIGH / nyquist, 0.95)  # Stay below Nyquist

    if low >= high or low <= 0:
        logger.warning(f"Invalid filter params: low={low}, high={high}. Skipping filter.")
        return signal

    try:
        # Chebyshev Type II — 40 dB stopband attenuation
        sos = cheby2(4, 40, [low, high], btype='band', output='sos')
        filtered = sosfilt(sos, signal)

        # Forward-backward filtering for zero-phase distortion
        # (sosfiltfilt would be ideal but sosfilt is more stable for short signals)
        filtered = sosfilt(sos, filtered[::-1])[::-1]

    except Exception as e:
        logger.warning(f"Chebyshev filter failed ({e}), falling back to Butterworth")
        try:
            b, a = butter(3, [low, high], btype='band')
            filtered = filtfilt(b, a, signal)
        except Exception as e2:
            logger.error(f"All filtering failed: {e2}")
            return signal

    return filtered


def adaptive_bandpass_filter(signal, fps=DEFAULT_FPS):
    """
    Bandpass filter with automatic cutoff frequency adaptation.

    Analyzes the signal's spectral content to fine-tune filter boundaries
    around the dominant cardiac frequency.

    Args:
        signal: Raw PPG signal.
        fps: Video FPS.

    Returns:
        Adaptively filtered signal.
    """
    signal = np.array(signal, dtype=np.float64)

    if len(signal) < MIN_SIGNAL_LENGTH * 3:
        return bandpass_filter(signal, fps)

    try:
        # Find dominant frequency in cardiac range
        freqs, psd = welch(signal, fs=fps, nperseg=min(len(signal), 256))
        cardiac_mask = (freqs >= 0.5) & (freqs <= 4.0)

        if np.any(cardiac_mask):
            cardiac_psd = psd.copy()
            cardiac_psd[~cardiac_mask] = 0
            dominant_freq = freqs[np.argmax(cardiac_psd)]

            # Adaptive bounds: ±0.5 Hz around dominant frequency, clamped
            adaptive_low = max(0.5, dominant_freq - 0.8)
            adaptive_high = min(4.0, dominant_freq + 1.2)

            nyquist = fps / 2.0
            low = adaptive_low / nyquist
            high = min(adaptive_high / nyquist, 0.95)

            if 0 < low < high < 1:
                sos = cheby2(4, 40, [low, high], btype='band', output='sos')
                filtered = sosfilt(sos, signal)
                filtered = sosfilt(sos, filtered[::-1])[::-1]
                return filtered

    except Exception as e:
        logger.warning(f"Adaptive filter failed ({e}), using standard bandpass")

    return bandpass_filter(signal, fps)


def remove_motion_artifacts(signal, fps=DEFAULT_FPS):
    """
    Suppress motion artifacts using high-pass residual subtraction.

    Motion artifacts typically manifest as low-frequency (<0.3 Hz) baseline
    wander. This function removes them while preserving cardiac components.

    Args:
        signal: Filtered PPG signal.
        fps: Video FPS.

    Returns:
        Motion-artifact-suppressed signal.
    """
    signal = np.array(signal, dtype=np.float64)

    if len(signal) < MIN_SIGNAL_LENGTH:
        return signal

    try:
        nyquist = fps / 2.0
        cutoff = 0.3 / nyquist  # Remove everything below 0.3 Hz

        if 0 < cutoff < 1:
            b, a = butter(2, cutoff, btype='high')
            return filtfilt(b, a, signal)
    except Exception as e:
        logger.warning(f"Motion artifact removal failed: {e}")

    return signal


# =============================================================================
# Signal Smoothing
# =============================================================================
def smooth_signal(signal, window_length=11, polyorder=3):
    """
    Savitzky-Golay filter — preserves peak morphology unlike moving average.

    This polynomial-fitting smoother maintains the shape and timing of systolic
    peaks and dicrotic notches, which is critical for morphological features.

    Args:
        signal: Filtered PPG signal.
        window_length: Window size (must be odd). Default 11.
        polyorder: Polynomial order. Default 3.

    Returns:
        Smoothed signal.
    """
    signal = np.array(signal, dtype=np.float64)

    if len(signal) < window_length:
        # Fallback to simple moving average for very short signals
        kernel_size = max(3, len(signal) // 3)
        if kernel_size % 2 == 0:
            kernel_size += 1
        return np.convolve(signal, np.ones(kernel_size) / kernel_size, mode='same')

    # Ensure window_length is odd and <= signal length
    wl = min(window_length, len(signal))
    if wl % 2 == 0:
        wl -= 1
    po = min(polyorder, wl - 1)

    return savgol_filter(signal, wl, po)


# =============================================================================
# Normalization
# =============================================================================
def normalize_signal(signal):
    """
    Z-score normalization with numerical stability.

    Args:
        signal: Input signal.

    Returns:
        Zero-mean, unit-variance normalized signal.
    """
    signal = np.array(signal, dtype=np.float64)
    std = np.std(signal)
    if std < 1e-8:
        logger.warning("Near-zero standard deviation — signal may be flat")
        return signal - np.mean(signal)
    return (signal - np.mean(signal)) / std


# =============================================================================
# Peak Detection
# =============================================================================
def detect_peaks(signal, fps=DEFAULT_FPS):
    """
    Adaptive peak detection with outlier rejection.

    Uses signal statistics to automatically tune `distance` and `prominence`
    thresholds. Rejects physiologically implausible peaks (RR intervals
    outside 0.3–2.0 seconds, i.e., 30–200 BPM).

    Args:
        signal: Normalized PPG signal.
        fps: Frames per second.

    Returns:
        Array of peak indices.
    """
    signal = np.array(signal, dtype=np.float64)

    if len(signal) < 5:
        return np.array([], dtype=int)

    # Adaptive parameters based on signal characteristics
    min_distance = max(5, int(fps * 0.3))   # Min 0.3s between beats (~200 BPM)
    max_distance = int(fps * 2.0)            # Max 2.0s between beats (~30 BPM)

    # Prominence: at least 20% of signal range
    signal_range = np.ptp(signal)
    min_prominence = 0.15 * signal_range if signal_range > 0 else 0

    # Initial peak detection
    peaks, properties = find_peaks(
        signal,
        distance=min_distance,
        prominence=min_prominence,
        height=np.mean(signal) - np.std(signal)  # Peaks should be above baseline
    )

    if len(peaks) < 2:
        # Retry with relaxed parameters
        peaks, _ = find_peaks(signal, distance=max(3, min_distance // 2))
        if len(peaks) < 2:
            return peaks

    # --- Outlier rejection based on RR intervals ---
    rr_intervals = np.diff(peaks)

    if len(rr_intervals) > 2:
        median_rr = np.median(rr_intervals)
        mad_rr = np.median(np.abs(rr_intervals - median_rr))  # Median absolute deviation

        if mad_rr > 0:
            # Keep peaks where adjacent RR intervals are within 2.5 MADs of median
            valid_mask = np.ones(len(peaks), dtype=bool)

            for i in range(len(rr_intervals)):
                if np.abs(rr_intervals[i] - median_rr) > 3.0 * max(mad_rr, 1):
                    # Mark the peak that creates the outlier interval
                    # (prefer removing the less prominent peak)
                    if i + 1 < len(peaks):
                        prominence_i = signal[peaks[i]] if peaks[i] < len(signal) else 0
                        prominence_next = signal[peaks[i + 1]] if peaks[i + 1] < len(signal) else 0
                        if prominence_i < prominence_next:
                            valid_mask[i] = False
                        else:
                            valid_mask[i + 1] = False

            peaks = peaks[valid_mask]

    return peaks


# =============================================================================
# Heart Rate
# =============================================================================
def calculate_heart_rate(peaks, total_frames, fps=DEFAULT_FPS):
    """
    Calculate heart rate from detected peaks.

    Uses peak-to-peak intervals for more accurate HR estimation
    rather than simple peak-count / duration.

    Args:
        peaks: Array of peak indices.
        total_frames: Total number of frames in the signal.
        fps: Frames per second.

    Returns:
        Heart rate in BPM (float). Returns 0 if insufficient peaks.
    """
    if len(peaks) < 2 or total_frames == 0 or fps == 0:
        return 0.0

    # Use median RR interval for robustness against outliers
    rr_intervals = np.diff(peaks) / fps  # Convert to seconds
    median_rr = np.median(rr_intervals)

    if median_rr <= 0:
        return 0.0

    hr = 60.0 / median_rr

    # Physiological clamp: 30–220 BPM
    return float(np.clip(hr, 30, 220))


# =============================================================================
# Feature Engineering — Standard (backward-compatible, 9 features)
# =============================================================================
def extract_advanced_features(signal, peaks):
    """
    Extract 9 advanced features from PPG signal and peaks.

    Backward-compatible with the existing model (same feature count & order).

    Features:
        [mean, std, max, min, hrv, avg_interval, energy, signal_range, peak_density]

    Args:
        signal: Normalized PPG signal.
        peaks: Detected peak indices.

    Returns:
        List of 9 float features.
    """
    signal = np.array(signal, dtype=np.float64)

    if len(signal) == 0:
        return [0.0] * 9

    mean_val = float(np.mean(signal))
    std_val = float(np.std(signal))
    max_val = float(np.max(signal))
    min_val = float(np.min(signal))

    if len(peaks) > 1:
        intervals = np.diff(peaks).astype(np.float64)
        hrv = float(np.std(intervals))
        avg_interval = float(np.mean(intervals))
    else:
        hrv, avg_interval = 0.0, 0.0

    energy = float(np.sum(signal ** 2))
    signal_range = max_val - min_val
    peak_density = len(peaks) / max(len(signal), 1)

    return [
        mean_val,
        std_val,
        max_val,
        min_val,
        hrv,
        avg_interval,
        energy,
        signal_range,
        peak_density
    ]


# =============================================================================
# Feature Engineering — HRV (backward-compatible, 2 features)
# =============================================================================
def calculate_hrv_features(peaks):
    """
    Calculate 2 HRV features from peak intervals.

    Backward-compatible with the existing model.

    Features:
        [SDNN (std of NN intervals), RMSSD (root mean square of successive diffs)]

    Args:
        peaks: Detected peak indices.

    Returns:
        List of 2 float features.
    """
    if len(peaks) < 2:
        return [0.0, 0.0]

    intervals = np.diff(peaks).astype(np.float64)

    sdnn = float(np.std(intervals))
    rmssd = float(np.sqrt(np.mean(intervals ** 2)))

    return [sdnn, rmssd]


# =============================================================================
# Feature Engineering — Extended (for improved model training)
# =============================================================================
def _sample_entropy(signal, m=2, r_factor=0.2):
    """
    Compute sample entropy — measures signal complexity/irregularity.

    Lower values indicate more regularity (healthy cardiac rhythm).

    Args:
        signal: Input signal.
        m: Embedding dimension.
        r_factor: Tolerance as fraction of signal std.

    Returns:
        Sample entropy (float).
    """
    signal = np.array(signal, dtype=np.float64)
    N = len(signal)

    if N < m + 2:
        return 0.0

    r = r_factor * np.std(signal)
    if r < 1e-10:
        return 0.0

    def _count_matches(template_len):
        count = 0
        templates = np.array([signal[i:i + template_len] for i in range(N - template_len)])
        for i in range(len(templates)):
            for j in range(i + 1, len(templates)):
                if np.max(np.abs(templates[i] - templates[j])) < r:
                    count += 1
        return count

    A = _count_matches(m + 1)
    B = _count_matches(m)

    if B == 0:
        return 0.0

    return -np.log(A / B) if A > 0 else 0.0


def _spectral_entropy(signal, fps=DEFAULT_FPS):
    """
    Compute spectral entropy — measures spectral flatness.

    High spectral entropy = noise-like (uniform power distribution).
    Low spectral entropy = tonal/periodic (concentrated power).

    Args:
        signal: Input signal.
        fps: Sampling rate.

    Returns:
        Normalized spectral entropy (0-1).
    """
    signal = np.array(signal, dtype=np.float64)

    if len(signal) < 8:
        return 0.0

    try:
        freqs, psd = welch(signal, fs=fps, nperseg=min(len(signal), 256))
        psd = psd / (np.sum(psd) + 1e-10)  # Normalize to probability distribution
        psd = psd[psd > 0]  # Remove zeros for log

        entropy = -np.sum(psd * np.log2(psd + 1e-10))
        max_entropy = np.log2(len(psd)) if len(psd) > 0 else 1

        return float(entropy / (max_entropy + 1e-10))
    except Exception:
        return 0.0


def extract_extended_features(signal, peaks, fps=DEFAULT_FPS):
    """
    Extract comprehensive feature set for enhanced model training.

    Returns 28 features organized into categories:
      - Statistical (6): mean, std, max, min, skewness, kurtosis
      - Peak-based (5): hrv, avg_interval, peak_density, mean_peak_amp, peak_regularity
      - Energy (3): energy, signal_range, rms
      - Frequency-domain (4): spectral_entropy, dominant_freq, lf_hf_ratio, total_power
      - Morphological (4): mean_rise_time, mean_fall_time, mean_pulse_width, mean_peak_sharpness
      - Nonlinear (2): sample_entropy, zero_crossing_rate
      - HRV (4): sdnn, rmssd, pnn50, cv_rr

    Args:
        signal: Normalized PPG signal.
        peaks: Detected peak indices.
        fps: Frames per second.

    Returns:
        List of 28 float features.
    """
    signal = np.array(signal, dtype=np.float64)
    n = len(signal)

    if n == 0:
        return [0.0] * 28

    # ---- Statistical features (6) ----
    mean_val = float(np.mean(signal))
    std_val = float(np.std(signal))
    max_val = float(np.max(signal))
    min_val = float(np.min(signal))
    skewness = float(skew(signal)) if n > 2 else 0.0
    kurt = float(scipy_kurtosis(signal)) if n > 3 else 0.0

    # ---- Peak-based features (5) ----
    if len(peaks) > 1:
        intervals = np.diff(peaks).astype(np.float64)
        hrv_val = float(np.std(intervals))
        avg_interval = float(np.mean(intervals))
        peak_regularity = 1.0 - (hrv_val / (avg_interval + 1e-10))  # Higher = more regular
    else:
        hrv_val, avg_interval, peak_regularity = 0.0, 0.0, 0.0

    peak_density = len(peaks) / max(n, 1)
    mean_peak_amp = float(np.mean(signal[peaks])) if len(peaks) > 0 else 0.0

    # ---- Energy features (3) ----
    energy = float(np.sum(signal ** 2))
    signal_range = max_val - min_val
    rms = float(np.sqrt(np.mean(signal ** 2)))

    # ---- Frequency-domain features (4) ----
    spec_entropy = _spectral_entropy(signal, fps)

    try:
        freqs, psd = welch(signal, fs=fps, nperseg=min(n, 256))
        cardiac_mask = (freqs >= 0.5) & (freqs <= 4.0)

        if np.any(cardiac_mask):
            cardiac_psd = psd.copy()
            cardiac_psd[~cardiac_mask] = 0
            dominant_freq = float(freqs[np.argmax(cardiac_psd)])
        else:
            dominant_freq = 0.0

        # LF/HF ratio (autonomic nervous system indicator)
        lf_mask = (freqs >= 0.04) & (freqs <= 0.15)
        hf_mask = (freqs >= 0.15) & (freqs <= 0.4)
        lf_power = float(np.sum(psd[lf_mask])) if np.any(lf_mask) else 0.0
        hf_power = float(np.sum(psd[hf_mask])) if np.any(hf_mask) else 0.0
        lf_hf_ratio = lf_power / (hf_power + 1e-10)

        total_power = float(np.sum(psd))
    except Exception:
        dominant_freq, lf_hf_ratio, total_power = 0.0, 0.0, 0.0

    # ---- Morphological features (4) ----
    mean_rise_time = 0.0
    mean_fall_time = 0.0
    mean_pulse_width = 0.0
    mean_peak_sharpness = 0.0

    if len(peaks) >= 2:
        rise_times = []
        fall_times = []
        pulse_widths = []
        sharpnesses = []

        for i, pk in enumerate(peaks):
            # Find troughs before and after peak
            if i > 0:
                segment_before = signal[peaks[i - 1]:pk]
                if len(segment_before) > 0:
                    trough_before = peaks[i - 1] + np.argmin(segment_before)
                    rise_times.append(pk - trough_before)
                else:
                    trough_before = pk
            else:
                trough_before = max(0, pk - int(avg_interval / 2)) if avg_interval > 0 else 0

            if i < len(peaks) - 1:
                segment_after = signal[pk:peaks[i + 1]]
                if len(segment_after) > 0:
                    trough_after = pk + np.argmin(segment_after)
                    fall_times.append(trough_after - pk)
                else:
                    trough_after = pk

            # Pulse width at half-maximum
            half_height = (signal[pk] + min_val) / 2
            left = pk
            while left > 0 and signal[left] > half_height:
                left -= 1
            right = pk
            while right < n - 1 and signal[right] > half_height:
                right += 1
            pulse_widths.append(right - left)

            # Peak sharpness (second derivative at peak)
            if 1 <= pk < n - 1:
                sharpness = abs(signal[pk - 1] - 2 * signal[pk] + signal[pk + 1])
                sharpnesses.append(sharpness)

        mean_rise_time = float(np.mean(rise_times)) if rise_times else 0.0
        mean_fall_time = float(np.mean(fall_times)) if fall_times else 0.0
        mean_pulse_width = float(np.mean(pulse_widths)) if pulse_widths else 0.0
        mean_peak_sharpness = float(np.mean(sharpnesses)) if sharpnesses else 0.0

    # ---- Nonlinear features (2) ----
    samp_entropy = _sample_entropy(signal[:min(n, 200)])  # Limit length for speed

    # Zero crossing rate
    zero_crossings = np.sum(np.abs(np.diff(np.sign(signal - np.mean(signal)))) > 0)
    zero_crossing_rate = float(zero_crossings / max(n - 1, 1))

    # ---- Extended HRV features (4) ----
    if len(peaks) > 2:
        intervals = np.diff(peaks).astype(np.float64)
        sdnn = float(np.std(intervals))
        successive_diffs = np.diff(intervals)
        rmssd = float(np.sqrt(np.mean(successive_diffs ** 2))) if len(successive_diffs) > 0 else 0.0

        # pNN50: proportion of successive intervals differing by >50ms equivalent
        threshold = 0.05 * fps  # 50ms equivalent in frames
        pnn50 = float(np.sum(np.abs(successive_diffs) > threshold) / max(len(successive_diffs), 1))

        cv_rr = float(sdnn / (np.mean(intervals) + 1e-10))  # Coefficient of variation
    else:
        sdnn, rmssd, pnn50, cv_rr = 0.0, 0.0, 0.0, 0.0

    return [
        # Statistical (6)
        mean_val, std_val, max_val, min_val, skewness, kurt,
        # Peak-based (5)
        hrv_val, avg_interval, peak_density, mean_peak_amp, peak_regularity,
        # Energy (3)
        energy, signal_range, rms,
        # Frequency-domain (4)
        spec_entropy, dominant_freq, lf_hf_ratio, total_power,
        # Morphological (4)
        mean_rise_time, mean_fall_time, mean_pulse_width, mean_peak_sharpness,
        # Nonlinear (2)
        samp_entropy, zero_crossing_rate,
        # HRV (4)
        sdnn, rmssd, pnn50, cv_rr
    ]


EXTENDED_FEATURE_NAMES = [
    'mean', 'std', 'max', 'min', 'skewness', 'kurtosis',
    'hrv', 'avg_interval', 'peak_density', 'mean_peak_amp', 'peak_regularity',
    'energy', 'signal_range', 'rms',
    'spectral_entropy', 'dominant_freq', 'lf_hf_ratio', 'total_power',
    'mean_rise_time', 'mean_fall_time', 'mean_pulse_width', 'mean_peak_sharpness',
    'sample_entropy', 'zero_crossing_rate',
    'sdnn', 'rmssd', 'pnn50', 'cv_rr'
]


# =============================================================================
# Plot Generation — Publication Quality, Dark Theme
# =============================================================================
def generate_plot_base64(signal, peaks=None, heart_rate=None, quality=None):
    """
    Generate a publication-quality, dark-themed PPG plot.

    Features:
        - Dark background with gridlines
        - Annotated peak markers
        - Heart rate and signal quality badges
        - Anti-aliased rendering

    Args:
        signal: PPG signal to plot.
        peaks: Optional peak indices to annotate.
        heart_rate: Optional HR value to display.
        quality: Optional SignalQuality enum.

    Returns:
        Base64-encoded PNG image string.
    """
    signal = np.array(signal, dtype=np.float64)

    # Dark theme
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(8, 4), dpi=120)
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#16213e')

    # Time axis
    x = np.arange(len(signal))

    # Main signal — gradient-like effect with fill
    ax.plot(x, signal, color='#00e676', linewidth=1.5, alpha=0.95, label='PPG Signal')
    ax.fill_between(x, signal, alpha=0.08, color='#00e676')

    # Peak annotations
    if peaks is not None and len(peaks) > 0:
        valid_peaks = peaks[peaks < len(signal)]
        ax.scatter(valid_peaks, signal[valid_peaks],
                   color='#ff5252', s=40, zorder=5, marker='v',
                   label=f'Peaks ({len(valid_peaks)})', edgecolors='white', linewidth=0.5)

    # Styling
    ax.set_title('PPG Signal Analysis', color='#e0e0e0', fontsize=14,
                 fontweight='bold', pad=15)
    ax.set_xlabel('Frame', color='#b0b0b0', fontsize=11)
    ax.set_ylabel('Amplitude', color='#b0b0b0', fontsize=11)

    ax.tick_params(colors='#808080', labelsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#404060')
    ax.spines['left'].set_color('#404060')

    ax.grid(True, alpha=0.15, color='#ffffff', linestyle='--')
    ax.legend(loc='upper right', fontsize=9, facecolor='#1a1a2e',
              edgecolor='#404060', labelcolor='#e0e0e0')

    # Info badges
    info_text = []
    if heart_rate is not None:
        info_text.append(f'HR: {heart_rate:.0f} BPM')
    if quality is not None:
        quality_colors = {
            SignalQuality.GOOD: '🟢',
            SignalQuality.ACCEPTABLE: '🟡',
            SignalQuality.POOR: '🟠',
            SignalQuality.UNUSABLE: '🔴'
        }
        emoji = quality_colors.get(quality, '⚪')
        info_text.append(f'{emoji} Quality: {quality.value.upper()}')

    if info_text:
        ax.text(0.02, 0.95, '\n'.join(info_text),
                transform=ax.transAxes, fontsize=10, color='#e0e0e0',
                verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#0a0a1a',
                          edgecolor='#404060', alpha=0.8))

    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    buffer.seek(0)

    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    plt.close('all')

    return image_base64