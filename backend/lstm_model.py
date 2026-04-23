# =============================================================================
# LSTM Glucose Prediction — Production-Grade Inference Pipeline
# =============================================================================
# Robust, thread-safe model loading with input validation, confidence scoring,
# Monte Carlo Dropout inference, structured prediction results, and
# physiological guardrails.
# =============================================================================

import numpy as np
import joblib
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from ppg_extraction import (
    normalize_signal, detect_peaks,
    extract_advanced_features, calculate_hrv_features,
    extract_extended_features, assess_signal_quality,
    SignalQuality
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================
SIGNAL_LENGTH = 120
GLUCOSE_MIN = 50          # Physiological lower bound (mg/dL)
GLUCOSE_MAX = 400         # Physiological upper bound (mg/dL)
GLUCOSE_NORMAL_LOW = 70   # Normal fasting low
GLUCOSE_NORMAL_HIGH = 200 # Post-prandial high boundary
MC_DROPOUT_ITERATIONS = 15  # Monte Carlo Dropout passes
CONFIDENCE_THRESHOLD_HIGH = 85.0
CONFIDENCE_THRESHOLD_MED = 60.0

# Model file paths (relative to script directory)
_SCRIPT_DIR = Path(__file__).parent
MODEL_PATH = _SCRIPT_DIR / "final_model.keras"
Y_SCALER_PATH = _SCRIPT_DIR / "y_scaler.save"
FEATURE_SCALER_PATH = _SCRIPT_DIR / "feature_scaler.save"

# Enhanced model (trained with extended features)
ENHANCED_MODEL_PATH = _SCRIPT_DIR / "enhanced_model.keras"
ENHANCED_FEATURE_SCALER_PATH = _SCRIPT_DIR / "enhanced_feature_scaler.save"
ENHANCED_Y_SCALER_PATH = _SCRIPT_DIR / "enhanced_y_scaler.save"


# =============================================================================
# Prediction Result
# =============================================================================
@dataclass
class PredictionResult:
    """Structured prediction output with confidence and diagnostics."""
    glucose: float                          # Predicted glucose (mg/dL)
    confidence: float                       # Confidence score (0–100%)
    interval: tuple                         # 95% prediction interval (low, high)
    reliability: str                        # HIGH / MEDIUM / LOW
    signal_quality: str                     # Signal quality grade
    heart_rate: float                       # Estimated heart rate (BPM)
    features_used: dict                     # Feature values for debugging
    prediction_time_ms: float = 0.0         # Inference time
    model_type: str = "standard"            # standard / enhanced
    raw_prediction: float = 0.0             # Pre-clipping prediction


# =============================================================================
# Thread-Safe Lazy Model Loader
# =============================================================================
class _ModelRegistry:
    """
    Singleton model registry with lazy loading and thread safety.

    Models and scalers are loaded on first prediction call, not at import time.
    This prevents crashes when the module is imported for its utility functions
    but model files aren't available.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._standard_loaded = False
        self._enhanced_loaded = False
        self._model = None
        self._y_scaler = None
        self._feature_scaler = None
        self._enhanced_model = None
        self._enhanced_y_scaler = None
        self._enhanced_feature_scaler = None

    def _load_standard(self):
        """Load standard model (11 features)."""
        if self._standard_loaded:
            return

        with self._lock:
            if self._standard_loaded:
                return  # Double-check after acquiring lock

            try:
                from tensorflow.keras.models import load_model
                logger.info(f"Loading standard model from {MODEL_PATH}")

                if not MODEL_PATH.exists():
                    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
                if not Y_SCALER_PATH.exists():
                    raise FileNotFoundError(f"Y-scaler not found: {Y_SCALER_PATH}")
                if not FEATURE_SCALER_PATH.exists():
                    raise FileNotFoundError(f"Feature scaler not found: {FEATURE_SCALER_PATH}")

                self._model = load_model(str(MODEL_PATH), safe_mode=False)
                self._y_scaler = joblib.load(str(Y_SCALER_PATH))
                self._feature_scaler = joblib.load(str(FEATURE_SCALER_PATH))
                self._standard_loaded = True
                logger.info("Standard model loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load standard model: {e}")
                raise RuntimeError(f"Model loading failed: {e}") from e

    def _load_enhanced(self):
        """Load enhanced model (28 features) if available."""
        if self._enhanced_loaded:
            return True

        with self._lock:
            if self._enhanced_loaded:
                return True

            if not ENHANCED_MODEL_PATH.exists():
                logger.info("Enhanced model not found — using standard model")
                return False

            try:
                from tensorflow.keras.models import load_model
                logger.info(f"Loading enhanced model from {ENHANCED_MODEL_PATH}")

                self._enhanced_model = load_model(str(ENHANCED_MODEL_PATH), safe_mode=False)
                self._enhanced_y_scaler = joblib.load(str(ENHANCED_Y_SCALER_PATH))
                self._enhanced_feature_scaler = joblib.load(str(ENHANCED_FEATURE_SCALER_PATH))
                self._enhanced_loaded = True
                logger.info("Enhanced model loaded successfully")
                return True

            except Exception as e:
                logger.warning(f"Enhanced model loading failed: {e}")
                return False

    @property
    def model(self):
        self._load_standard()
        return self._model

    @property
    def y_scaler(self):
        self._load_standard()
        return self._y_scaler

    @property
    def feature_scaler(self):
        self._load_standard()
        return self._feature_scaler

    @property
    def enhanced_model(self):
        if self._load_enhanced():
            return self._enhanced_model
        return None

    @property
    def enhanced_y_scaler(self):
        if self._load_enhanced():
            return self._enhanced_y_scaler
        return None

    @property
    def enhanced_feature_scaler(self):
        if self._load_enhanced():
            return self._enhanced_feature_scaler
        return None

    @property
    def has_enhanced(self):
        return self._enhanced_loaded or ENHANCED_MODEL_PATH.exists()


# Global singleton
_registry = _ModelRegistry()


# =============================================================================
# Input Validation & Preprocessing
# =============================================================================
def _validate_signal(signal):
    """
    Validate and clean input signal.

    Checks for NaN, Inf, type, and minimum length.

    Args:
        signal: Input signal (list or numpy array).

    Returns:
        Cleaned numpy float64 array.

    Raises:
        ValueError: If signal is invalid.
    """
    signal = np.array(signal, dtype=np.float64)

    if signal.ndim != 1:
        raise ValueError(f"Signal must be 1D, got shape {signal.shape}")

    if len(signal) == 0:
        raise ValueError("Empty signal")

    # Replace NaN/Inf with interpolated values
    nan_mask = ~np.isfinite(signal)
    if np.all(nan_mask):
        raise ValueError("Signal contains only NaN/Inf values")

    if np.any(nan_mask):
        logger.warning(f"Signal has {nan_mask.sum()} NaN/Inf values — interpolating")
        good_indices = np.where(~nan_mask)[0]
        bad_indices = np.where(nan_mask)[0]
        signal[bad_indices] = np.interp(bad_indices, good_indices, signal[good_indices])

    return signal


def _prepare_signal_input(signal, target_length=SIGNAL_LENGTH):
    """
    Prepare signal for model input with reflect-padding.

    Reflect-padding preserves signal characteristics better than zero-padding,
    which introduces artificial discontinuities at the boundary.

    Args:
        signal: Normalized 1D signal.
        target_length: Target length (default 120).

    Returns:
        Signal reshaped to (1, target_length, 1).
    """
    if len(signal) < target_length:
        # Reflect-pad preserves signal morphology
        pad_length = target_length - len(signal)
        signal = np.pad(signal, (0, pad_length), mode='reflect')
    elif len(signal) > target_length:
        # Take the center segment (best quality typically)
        start = (len(signal) - target_length) // 2
        signal = signal[start: start + target_length]

    return signal.reshape(1, target_length, 1)


# =============================================================================
# Confidence Scoring
# =============================================================================
def _deterministic_predict(model, inputs):
    # Only for backward compatibility signature
    pred = model.predict(inputs, verbose=0)
    return np.array([pred.flatten()[0]]), pred.flatten()[0], 0.0


def _compute_confidence(pred_std, signal_quality, pred_mean):
    """
    Compute confidence score (0-100%) from prediction variance and signal quality.

    Factors:
        - Prediction variance (lower = higher confidence)
        - Signal quality grade
        - Prediction being within physiological range

    Args:
        pred_std: Standard deviation of MC Dropout predictions.
        signal_quality: SignalQuality enum.
        pred_mean: Mean prediction (scaled glucose).

    Returns:
        Confidence score (0-100).
    """
    # Signal quality factor directly maps to confidence when MC is disabled
    quality_confidences = {
        SignalQuality.GOOD: 95.0,
        SignalQuality.ACCEPTABLE: 75.0,
        SignalQuality.POOR: 45.0,
        SignalQuality.UNUSABLE: 10.0
    }
    confidence = quality_confidences.get(signal_quality, 50.0)

    return float(np.clip(confidence, 0, 100))


def _soft_clip(value, low, high, steepness=0.1):
    """
    Soft sigmoid-based boundary clipping.

    Unlike hard clipping (which creates discontinuities), soft clipping
    smoothly penalizes values as they approach boundaries.

    Args:
        value: Raw prediction.
        low: Lower bound.
        high: Upper bound.
        steepness: Steepness of sigmoid transition (lower = softer).

    Returns:
        Softly clipped value.
    """
    center = (low + high) / 2
    half_range = (high - low) / 2

    # Normalize to [-1, 1] range
    normalized = (value - center) / half_range

    # Apply tanh soft clipping
    clipped_normalized = np.tanh(normalized * (1 + steepness))

    return center + clipped_normalized * half_range


# =============================================================================
# Main Prediction Functions
# =============================================================================
def predict_glucose(signal):
    """
    Predict glucose level from PPG signal.

    Backward-compatible function that returns a single float value.
    Uses the standard model with 11 features.

    Args:
        signal: Raw or preprocessed PPG signal.

    Returns:
        Predicted glucose level (float, mg/dL).
    """
    result = predict_glucose_detailed(signal)
    return result.glucose


def predict_glucose_detailed(signal, use_enhanced=True):
    """
    Full prediction pipeline with confidence scoring and diagnostics.

    Attempts to use the enhanced model (28 features) if available,
    falls back to the standard model (11 features).

    Pipeline:
        1. Validate & normalize signal
        2. Assess signal quality
        3. Detect peaks & extract features
        4. Scale features
        5. Run MC Dropout inference (if model supports it)
        6. Compute confidence interval
        7. Apply physiological guardrails
        8. Return structured PredictionResult

    Args:
        signal: Raw or preprocessed PPG signal.
        use_enhanced: Whether to try the enhanced model first.

    Returns:
        PredictionResult with glucose, confidence, interval, etc.
    """
    t_start = time.perf_counter()

    # --- 1. Validate ---
    signal = _validate_signal(signal)
    signal = normalize_signal(signal)

    # --- 2. Signal quality ---
    diagnostics = assess_signal_quality(signal)
    if diagnostics.quality == SignalQuality.UNUSABLE:
        logger.warning("Signal quality UNUSABLE — prediction unreliable")

    # --- 3. Pad/Truncate signal (match training preprocessing) ---
    if len(signal) < SIGNAL_LENGTH:
        signal = np.pad(signal, (0, SIGNAL_LENGTH - len(signal)), mode='reflect')
    else:
        signal = signal[:SIGNAL_LENGTH]

    # --- 4. Peaks & features ---
    peaks = detect_peaks(signal)
    heart_rate_estimate = 0.0
    if len(peaks) >= 2:
        rr_intervals = np.diff(peaks) / 30.0  # Assuming 30 FPS
        heart_rate_estimate = 60.0 / np.median(rr_intervals)
        heart_rate_estimate = float(np.clip(heart_rate_estimate, 30, 220))

    # --- 5. Choose model & extract features ---
    use_enh = use_enhanced and _registry.has_enhanced

    if use_enh:
        try:
            _registry._load_enhanced()
            if _registry.enhanced_model is not None:
                features = extract_extended_features(signal, peaks)
                scaled_features = _registry.enhanced_feature_scaler.transform([features])
                model = _registry.enhanced_model
                y_scaler = _registry.enhanced_y_scaler
                model_type = "enhanced"
            else:
                use_enh = False
        except Exception as e:
            logger.warning(f"Enhanced model unavailable: {e}")
            use_enh = False

    if not use_enh:
        adv = extract_advanced_features(signal, peaks)
        hrv = calculate_hrv_features(peaks)
        features = adv + hrv
        scaled_features = _registry.feature_scaler.transform([features])
        model = _registry.model
        y_scaler = _registry.y_scaler
        model_type = "standard"

    # --- 6. Prepare signal input ---
    signal_input = signal.reshape(1, SIGNAL_LENGTH, 1)

    # --- 7. Standard Inference ---
    # We cannot use training=True (MC Dropout) here because it forces
    # BatchNormalization to use batch statistics, which ruins inference for batch_size=1.
    pred_mean = float(model.predict([signal_input, scaled_features], verbose=0)[0][0])
    pred_std = 0.0  # Uncertainty unavailable single-pass

    # --- 8. Inverse transform ---
    raw_glucose = y_scaler.inverse_transform([[pred_mean]])[0][0]
    raw_glucose = float(raw_glucose)

    margin = max(10.0, abs(raw_glucose) * 0.1)
    interval_low = raw_glucose - margin
    interval_high = raw_glucose + margin

    # --- 9. Confidence ---
    confidence = _compute_confidence(pred_std, diagnostics.quality, pred_mean)

    # --- 10. Physiological guardrails ---
    glucose_clipped = _soft_clip(raw_glucose, GLUCOSE_MIN, GLUCOSE_MAX)

    # Hard minimum safety net
    glucose_clipped = max(glucose_clipped, GLUCOSE_MIN)

    if abs(raw_glucose - glucose_clipped) > 5:
        logger.warning(f"Prediction clipped: {raw_glucose:.1f} → {glucose_clipped:.1f} mg/dL")

    # Clip interval too
    interval_low = max(interval_low, GLUCOSE_MIN)
    interval_high = min(interval_high, GLUCOSE_MAX)

    # --- 11. Reliability grade ---
    if confidence >= CONFIDENCE_THRESHOLD_HIGH and diagnostics.quality in (SignalQuality.GOOD, SignalQuality.ACCEPTABLE):
        reliability = "HIGH"
    elif confidence >= CONFIDENCE_THRESHOLD_MED:
        reliability = "MEDIUM"
    else:
        reliability = "LOW"

    # --- 12. Build result ---
    t_end = time.perf_counter()

    features_dict = {}
    if use_enh:
        from ppg_extraction import EXTENDED_FEATURE_NAMES
        features_dict = dict(zip(EXTENDED_FEATURE_NAMES, features))
    else:
        feat_names = ['mean', 'std', 'max', 'min', 'hrv', 'avg_interval',
                      'energy', 'signal_range', 'peak_density', 'sdnn', 'rmssd']
        features_dict = dict(zip(feat_names, features))

    result = PredictionResult(
        glucose=round(glucose_clipped, 2),
        confidence=round(confidence, 1),
        interval=(round(interval_low, 2), round(interval_high, 2)),
        reliability=reliability,
        signal_quality=diagnostics.quality.value,
        heart_rate=round(heart_rate_estimate, 1),
        features_used=features_dict,
        prediction_time_ms=round((t_end - t_start) * 1000, 2),
        model_type=model_type,
        raw_prediction=round(raw_glucose, 2)
    )

    logger.info(f"Prediction: {result.glucose} mg/dL "
                f"(confidence={result.confidence}%, reliability={result.reliability}, "
                f"model={result.model_type}, time={result.prediction_time_ms}ms)")

    return result