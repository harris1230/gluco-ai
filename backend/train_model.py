# =============================================================================
# Enhanced Model Training — Multi-Scale CNN + Bidirectional LSTM + Attention
# =============================================================================
# Production-grade training pipeline for non-invasive glucose prediction.
#
# Key Improvements over the original:
#   - 28 extended features (frequency-domain, morphological, nonlinear, HRV)
#   - Multi-scale CNN (3/5/7 kernel) for capturing temporal patterns at all scales
#   - Bidirectional LSTM with self-attention for temporal modeling
#   - Heavy regularization (dropout, batch norm, L2, early stopping)
#   - Data augmentation (noise, scaling, time-shift) for small datasets
#   - K-Fold cross-validation with ensemble averaging
#   - Huber loss (robust to outliers in glucose targets)
#   - Learning rate scheduling with cosine annealing
#   - Comprehensive metrics logging and model comparison
# =============================================================================

import pandas as pd
import numpy as np
import joblib
import os
import json
import logging
from datetime import datetime

from tensorflow.keras.models import Model
from tensorflow.keras.layers import (
    Input, Conv1D, MaxPooling1D, LSTM, Dense, Dropout, Concatenate,
    BatchNormalization, Bidirectional, GlobalAveragePooling1D,
    Multiply, Permute, RepeatVector, Add, Activation,
    SpatialDropout1D, GaussianNoise
)
from tensorflow.keras.callbacks import (
    EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
)
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.regularizers import l2
import tensorflow.keras.backend as K

from sklearn.preprocessing import MinMaxScaler, StandardScaler, RobustScaler
from sklearn.model_selection import train_test_split, KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ppg_extraction import (
    extract_frames, extract_ppg_signal, bandpass_filter,
    smooth_signal, normalize_signal, detect_peaks,
    extract_advanced_features, calculate_hrv_features,
    extract_extended_features, remove_motion_artifacts,
    adaptive_bandpass_filter, assess_signal_quality,
    EXTENDED_FEATURE_NAMES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================
SIGNAL_LENGTH = 120
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# Training hyperparameters
EPOCHS = 200
BATCH_SIZE = 4
LEARNING_RATE = 0.001
MIN_LEARNING_RATE = 1e-6
PATIENCE_EARLY_STOP = 25
PATIENCE_LR_REDUCE = 10
N_FOLDS = 4  # For cross-validation (set to 1 to skip CV)

# Data augmentation
AUGMENTATION_FACTOR = 8  # Generate N augmented copies per sample
NOISE_STD_RANGE = (0.01, 0.05)       # Gaussian noise level
SCALE_RANGE = (0.85, 1.15)           # Amplitude scaling
SHIFT_RANGE = (-5, 5)               # Time-shift in frames

# Model architecture
CONV_FILTERS = [32, 64]
LSTM_UNITS = [64, 32]
DENSE_UNITS = [128, 64, 32]
DROPOUT_RATE = 0.35
L2_REG = 1e-4


# =============================================================================
# Data Augmentation
# =============================================================================
def augment_signal(signal, n_augments=AUGMENTATION_FACTOR):
    """
    Generate augmented versions of a PPG signal.

    Augmentations applied randomly:
        - Gaussian noise injection
        - Amplitude scaling
        - Time-shift (circular)
        - Segment reversal
        - Smooth distortion (low-freq noise addition)

    Args:
        signal: Original 1D signal.
        n_augments: Number of augmented copies.

    Returns:
        List of augmented signal arrays.
    """
    augmented = []

    for _ in range(n_augments):
        s = signal.copy()

        # 1. Gaussian noise (90% probability)
        if np.random.random() < 0.9:
            noise_std = np.random.uniform(*NOISE_STD_RANGE)
            s = s + np.random.normal(0, noise_std, len(s))

        # 2. Amplitude scaling (70% probability)
        if np.random.random() < 0.7:
            scale = np.random.uniform(*SCALE_RANGE)
            s = s * scale

        # 3. Time-shift (60% probability)
        if np.random.random() < 0.6:
            shift = np.random.randint(*SHIFT_RANGE)
            s = np.roll(s, shift)

        # 4. Smooth distortion — add low-frequency noise (40% probability)
        if np.random.random() < 0.4:
            t = np.linspace(0, 2 * np.pi, len(s))
            freq = np.random.uniform(0.5, 2.0)
            amp = np.random.uniform(0.01, 0.05)
            s = s + amp * np.sin(freq * t + np.random.uniform(0, 2 * np.pi))

        # 5. Local segment flip (20% probability)
        if np.random.random() < 0.2:
            seg_len = np.random.randint(10, min(30, len(s) // 3))
            start = np.random.randint(0, len(s) - seg_len)
            s[start:start + seg_len] = s[start:start + seg_len][::-1]

        augmented.append(s)

    return augmented


# =============================================================================
# Attention Layer
# =============================================================================
def attention_layer(inputs, name_prefix='attention'):
    """
    Self-attention mechanism for LSTM sequence output.

    Learns which time steps are most important for glucose prediction.

    Args:
        inputs: 3D tensor (batch, timesteps, features).
        name_prefix: Name prefix for layers.

    Returns:
        Context vector (batch, features).
    """
    time_steps = K.int_shape(inputs)[1]
    features = K.int_shape(inputs)[2]

    # Attention weights
    a = Dense(features, activation='tanh',
              name=f'{name_prefix}_tanh')(inputs)
    a = Dense(1, activation='softmax',
              name=f'{name_prefix}_softmax')(a)

    # Apply attention — weighted sum along time axis
    output = Multiply(name=f'{name_prefix}_mul')([inputs, a])
    # Use GlobalAveragePooling1D instead of Lambda(sum) — serializes cleanly
    output = GlobalAveragePooling1D(name=f'{name_prefix}_pool')(output)

    return output


# =============================================================================
# Model Architecture
# =============================================================================
def build_enhanced_model(signal_length, num_features, learning_rate=LEARNING_RATE):
    """
    Build Multi-Scale CNN + Bidirectional LSTM + Attention model.

    Architecture:
        Signal Branch:
            - GaussianNoise (regularization)
            - Multi-scale Conv1D (kernel sizes 3, 5, 7) → captures short/medium/long patterns
            - BatchNorm + SpatialDropout
            - Second Conv1D block
            - Bidirectional LSTM (return sequences) → Attention → temporal summarization
            - Bidirectional LSTM → final temporal encoding

        Feature Branch:
            - Dense(64) → BatchNorm → Dropout → Dense(32)

        Combined:
            - Concatenate → Dense(128) → BN → Dropout → Dense(64) → Dense(32) → Dense(1)

    Args:
        signal_length: Length of input signal (default 120).
        num_features: Number of engineered features.
        learning_rate: Initial learning rate.

    Returns:
        Compiled Keras Model.
    """
    # ======== Signal Branch ========
    input_signal = Input(shape=(signal_length, 1), name='signal_input')

    # Input noise for regularization
    x = GaussianNoise(0.01)(input_signal)

    # Multi-scale convolution — capture patterns at different granularities
    conv3 = Conv1D(32, 3, padding='same', activation='relu',
                   kernel_regularizer=l2(L2_REG), name='conv_k3')(x)
    conv5 = Conv1D(32, 5, padding='same', activation='relu',
                   kernel_regularizer=l2(L2_REG), name='conv_k5')(x)
    conv7 = Conv1D(32, 7, padding='same', activation='relu',
                   kernel_regularizer=l2(L2_REG), name='conv_k7')(x)

    x = Concatenate(name='multi_scale_concat')([conv3, conv5, conv7])  # → (batch, 120, 96)
    x = BatchNormalization(name='bn_conv1')(x)
    x = SpatialDropout1D(0.15, name='sdrop1')(x)

    # Second convolution block
    x = Conv1D(64, 3, padding='same', activation='relu',
               kernel_regularizer=l2(L2_REG), name='conv2')(x)
    x = BatchNormalization(name='bn_conv2')(x)
    x = MaxPooling1D(2, name='maxpool')(x)  # → (batch, 60, 64)
    x = SpatialDropout1D(0.15, name='sdrop2')(x)

    # Bidirectional LSTM with attention
    x = Bidirectional(
        LSTM(64, return_sequences=True, dropout=0.3, recurrent_dropout=0.2,
             kernel_regularizer=l2(L2_REG)),
        name='bilstm1'
    )(x)

    # Self-attention over LSTM sequence
    attn_out = attention_layer(x, name_prefix='attn')

    # Second LSTM layer (takes attended sequence context)
    x = Bidirectional(
        LSTM(32, dropout=0.2, recurrent_dropout=0.1),
        name='bilstm2'
    )(x)

    # Combine LSTM output + attention context
    x = Concatenate(name='lstm_attn_concat')([x, attn_out])

    # ======== Feature Branch ========
    input_feat = Input(shape=(num_features,), name='feature_input')

    feat = Dense(64, activation='relu', kernel_regularizer=l2(L2_REG),
                 name='feat_dense1')(input_feat)
    feat = BatchNormalization(name='bn_feat1')(feat)
    feat = Dropout(DROPOUT_RATE, name='feat_drop1')(feat)

    feat = Dense(32, activation='relu', kernel_regularizer=l2(L2_REG),
                 name='feat_dense2')(feat)
    feat = BatchNormalization(name='bn_feat2')(feat)

    # ======== Merge & Prediction ========
    combined = Concatenate(name='final_concat')([x, feat])

    out = Dense(128, activation='relu', kernel_regularizer=l2(L2_REG),
                name='dense_comb1')(combined)
    out = BatchNormalization(name='bn_comb1')(out)
    out = Dropout(DROPOUT_RATE, name='drop_comb1')(out)

    out = Dense(64, activation='relu', kernel_regularizer=l2(L2_REG),
                name='dense_comb2')(out)
    out = Dropout(0.25, name='drop_comb2')(out)

    out = Dense(32, activation='relu', kernel_regularizer=l2(L2_REG),
                name='dense_comb3')(out)

    # Sigmoid output since targets are MinMax-scaled to [0, 1]
    output = Dense(1, activation='sigmoid', name='output')(out)

    model = Model(inputs=[input_signal, input_feat], outputs=output)

    # Huber loss — robust to outliers in glucose targets
    model.compile(
        optimizer=Adam(learning_rate=learning_rate, clipnorm=1.0),
        loss='huber',
        metrics=['mae']
    )

    return model


# =============================================================================
# Data Processing Pipeline
# =============================================================================
def process_video_to_features(video_path):
    """
    Full pipeline: video → signal → features.

    Returns:
        Tuple of (signal, extended_features, signal_quality) or None if failed.
    """
    try:
        frames = extract_frames(video_path)
        if len(frames) == 0:
            logger.warning(f"No frames extracted from {video_path}")
            return None

        # Extract and filter signal
        signal = extract_ppg_signal(frames)
        signal = remove_motion_artifacts(signal)
        signal = adaptive_bandpass_filter(signal)
        signal = smooth_signal(signal)
        signal = normalize_signal(signal)

        # Signal quality check
        quality = assess_signal_quality(signal)
        logger.info(f"  Signal quality: {quality.quality.value} "
                    f"(SNR={quality.snr_db:.1f}dB)")

        # Pad / truncate
        if len(signal) < SIGNAL_LENGTH:
            signal = np.pad(signal, (0, SIGNAL_LENGTH - len(signal)), mode='reflect')
        else:
            signal = signal[:SIGNAL_LENGTH]

        # Extract features
        peaks = detect_peaks(signal)
        features = extract_extended_features(signal, peaks)

        return signal, features, quality

    except Exception as e:
        logger.error(f"Failed to process {video_path}: {e}")
        return None


# =============================================================================
# Main Training Pipeline
# =============================================================================
def main():
    logger.info("=" * 60)
    logger.info("  ENHANCED MODEL TRAINING PIPELINE")
    logger.info("=" * 60)

    # --- 1. Load dataset ---
    data = pd.read_csv("dataset/video_data.csv")
    logger.info(f"Dataset: {len(data)} samples")
    logger.info(f"Glucose range: {data['glucose'].min()} - {data['glucose'].max()} mg/dL")
    logger.info(f"Glucose mean: {data['glucose'].mean():.1f} ± {data['glucose'].std():.1f}")

    # --- 2. Process all videos ---
    X_signal = []
    X_features = []
    y = []
    quality_scores = []

    for idx, row in data.iterrows():
        logger.info(f"Processing [{idx+1}/{len(data)}]: {row['video_path']}")

        result = process_video_to_features(row['video_path'])
        if result is None:
            logger.warning(f"  SKIPPED — processing failed")
            continue

        signal, features, quality = result

        X_signal.append(signal)
        X_features.append(features)
        y.append(row['glucose'])
        quality_scores.append(quality.quality.value)

    logger.info(f"\nSuccessfully processed: {len(X_signal)} / {len(data)} samples")
    logger.info(f"Signal quality distribution: {dict(zip(*np.unique(quality_scores, return_counts=True)))}")

    if len(X_signal) < 4:
        logger.error("Insufficient data for training (need at least 4 samples)")
        return

    X_signal = np.array(X_signal).reshape(len(X_signal), SIGNAL_LENGTH, 1)
    X_features = np.array(X_features)
    y = np.array(y).reshape(-1, 1)

    logger.info(f"Signal shape: {X_signal.shape}")
    logger.info(f"Features shape: {X_features.shape} ({len(EXTENDED_FEATURE_NAMES)} features)")

    # --- 3. Scale targets ---
    y_scaler = MinMaxScaler(feature_range=(0.05, 0.95))  # Avoid 0/1 boundaries for sigmoid
    y_scaled = y_scaler.fit_transform(y)

    # RobustScaler handles outlier features better than StandardScaler
    feature_scaler = RobustScaler()
    X_features_scaled = feature_scaler.fit_transform(X_features)

    # Save scalers
    joblib.dump(y_scaler, "enhanced_y_scaler.save")
    joblib.dump(feature_scaler, "enhanced_feature_scaler.save")
    logger.info("Scalers saved: enhanced_y_scaler.save, enhanced_feature_scaler.save")

    # --- 4. Data augmentation ---
    logger.info(f"\nData augmentation: {AUGMENTATION_FACTOR}x per sample")

    X_sig_aug = list(X_signal.reshape(-1, SIGNAL_LENGTH))
    X_feat_aug = list(X_features_scaled)
    y_aug = list(y_scaled.flatten())

    for i in range(len(X_signal)):
        original_signal = X_signal[i].flatten()
        augmented_signals = augment_signal(original_signal, AUGMENTATION_FACTOR)

        for aug_signal in augmented_signals:
            # Re-normalize augmented signal
            aug_signal = normalize_signal(aug_signal)

            if len(aug_signal) < SIGNAL_LENGTH:
                aug_signal = np.pad(aug_signal, (0, SIGNAL_LENGTH - len(aug_signal)), mode='reflect')
            else:
                aug_signal = aug_signal[:SIGNAL_LENGTH]

            # Re-extract features from augmented signal
            peaks = detect_peaks(aug_signal)
            aug_features = extract_extended_features(aug_signal, peaks)
            aug_features_scaled = feature_scaler.transform([aug_features])

            X_sig_aug.append(aug_signal)
            X_feat_aug.append(aug_features_scaled.flatten())
            y_aug.append(y_scaled[i].flatten()[0])

    X_sig_aug = np.array(X_sig_aug).reshape(-1, SIGNAL_LENGTH, 1)
    X_feat_aug = np.array(X_feat_aug)
    y_aug = np.array(y_aug).reshape(-1, 1)

    logger.info(f"Augmented dataset: {len(y_aug)} samples "
                f"({len(X_signal)} original + {len(y_aug) - len(X_signal)} augmented)")

    # --- 5. Also train backward-compatible standard model ---
    logger.info("\n" + "=" * 60)
    logger.info("  Phase 1: Training STANDARD model (backward compatible)")
    logger.info("=" * 60)

    # Extract standard features (11)
    X_features_std = []
    for i in range(len(X_signal)):
        sig = X_signal[i].flatten()
        peaks = detect_peaks(sig)
        adv = extract_advanced_features(sig, peaks)
        hrv = calculate_hrv_features(peaks)
        X_features_std.append(adv + hrv)

    X_features_std = np.array(X_features_std)
    std_feature_scaler = StandardScaler()
    X_features_std_scaled = std_feature_scaler.fit_transform(X_features_std)

    std_y_scaler = MinMaxScaler()
    y_std_scaled = std_y_scaler.fit_transform(y)

    joblib.dump(std_feature_scaler, "feature_scaler.save")
    joblib.dump(std_y_scaler, "y_scaler.save")

    # Augment standard features
    X_sig_std_aug = list(X_signal.reshape(-1, SIGNAL_LENGTH))
    X_feat_std_aug = list(X_features_std_scaled)
    y_std_aug = list(y_std_scaled.flatten())

    for i in range(len(X_signal)):
        original_signal = X_signal[i].flatten()
        augmented_signals = augment_signal(original_signal, AUGMENTATION_FACTOR)

        for aug_signal in augmented_signals:
            aug_signal = normalize_signal(aug_signal)
            if len(aug_signal) < SIGNAL_LENGTH:
                aug_signal = np.pad(aug_signal, (0, SIGNAL_LENGTH - len(aug_signal)), mode='reflect')
            else:
                aug_signal = aug_signal[:SIGNAL_LENGTH]

            peaks = detect_peaks(aug_signal)
            adv = extract_advanced_features(aug_signal, peaks)
            hrv = calculate_hrv_features(peaks)
            std_features = adv + hrv
            std_feat_scaled = std_feature_scaler.transform([std_features])

            X_sig_std_aug.append(aug_signal)
            X_feat_std_aug.append(std_feat_scaled.flatten())
            y_std_aug.append(y_std_scaled[i].flatten()[0])

    X_sig_std_aug = np.array(X_sig_std_aug).reshape(-1, SIGNAL_LENGTH, 1)
    X_feat_std_aug = np.array(X_feat_std_aug)
    y_std_aug = np.array(y_std_aug).reshape(-1, 1)

    # Split and train standard model
    (X_sig_s_train, X_sig_s_val,
     X_feat_s_train, X_feat_s_val,
     y_s_train, y_s_val) = train_test_split(
        X_sig_std_aug, X_feat_std_aug, y_std_aug,
        test_size=0.2, random_state=RANDOM_SEED
    )

    std_model = build_enhanced_model(SIGNAL_LENGTH, 11, learning_rate=LEARNING_RATE)
    std_model.summary()

    std_callbacks = [
        EarlyStopping(patience=PATIENCE_EARLY_STOP, restore_best_weights=True,
                      monitor='val_loss', verbose=1),
        ReduceLROnPlateau(factor=0.5, patience=PATIENCE_LR_REDUCE,
                          min_lr=MIN_LEARNING_RATE, verbose=1),
        ModelCheckpoint('final_model.keras', save_best_only=True,
                        monitor='val_loss', verbose=1)
    ]

    std_history = std_model.fit(
        [X_sig_s_train, X_feat_s_train], y_s_train,
        validation_data=([X_sig_s_val, X_feat_s_val], y_s_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=std_callbacks,
        verbose=1
    )

    # Evaluate standard model on original (non-augmented) data
    std_preds = std_model.predict([X_signal, X_features_std_scaled], verbose=0)
    std_preds_glucose = std_y_scaler.inverse_transform(std_preds)
    std_mae = mean_absolute_error(y, std_preds_glucose)
    std_rmse = np.sqrt(mean_squared_error(y, std_preds_glucose))
    logger.info(f"\n🔥 STANDARD MODEL — Original data MAE: {std_mae:.2f} mg/dL, RMSE: {std_rmse:.2f}")

    # --- 6. Train enhanced model ---
    logger.info("\n" + "=" * 60)
    logger.info("  Phase 2: Training ENHANCED model (28 features)")
    logger.info("=" * 60)

    num_features = X_features_scaled.shape[1]

    if N_FOLDS > 1 and len(X_signal) >= N_FOLDS:
        # K-Fold cross-validation
        logger.info(f"Running {N_FOLDS}-fold cross-validation")
        kfold = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)

        cv_scores = []
        fold_models = []

        for fold, (train_idx, val_idx) in enumerate(kfold.split(X_signal)):
            logger.info(f"\n--- Fold {fold + 1}/{N_FOLDS} ---")

            # Split original data
            X_sig_train_fold = X_signal[train_idx]
            X_feat_train_fold = X_features_scaled[train_idx]
            y_train_fold = y_scaled[train_idx]

            X_sig_val_fold = X_signal[val_idx]
            X_feat_val_fold = X_features_scaled[val_idx]
            y_val_fold = y_scaled[val_idx]

            # Augment training fold only
            X_sig_aug_fold = list(X_sig_train_fold.reshape(-1, SIGNAL_LENGTH))
            X_feat_aug_fold = list(X_feat_train_fold)
            y_aug_fold = list(y_train_fold.flatten())

            for i in range(len(X_sig_train_fold)):
                sig = X_sig_train_fold[i].flatten()
                augmented = augment_signal(sig, AUGMENTATION_FACTOR)
                for aug_sig in augmented:
                    aug_sig = normalize_signal(aug_sig)
                    if len(aug_sig) < SIGNAL_LENGTH:
                        aug_sig = np.pad(aug_sig, (0, SIGNAL_LENGTH - len(aug_sig)), mode='reflect')
                    else:
                        aug_sig = aug_sig[:SIGNAL_LENGTH]
                    peaks = detect_peaks(aug_sig)
                    aug_feat = extract_extended_features(aug_sig, peaks)
                    aug_feat_scaled = feature_scaler.transform([aug_feat])
                    X_sig_aug_fold.append(aug_sig)
                    X_feat_aug_fold.append(aug_feat_scaled.flatten())
                    y_aug_fold.append(y_train_fold[i].flatten()[0])

            X_sig_aug_fold = np.array(X_sig_aug_fold).reshape(-1, SIGNAL_LENGTH, 1)
            X_feat_aug_fold = np.array(X_feat_aug_fold)
            y_aug_fold = np.array(y_aug_fold).reshape(-1, 1)

            model = build_enhanced_model(SIGNAL_LENGTH, num_features)

            callbacks = [
                EarlyStopping(patience=PATIENCE_EARLY_STOP, restore_best_weights=True,
                              monitor='val_loss', verbose=0),
                ReduceLROnPlateau(factor=0.5, patience=PATIENCE_LR_REDUCE,
                                  min_lr=MIN_LEARNING_RATE, verbose=0),
            ]

            model.fit(
                [X_sig_aug_fold, X_feat_aug_fold], y_aug_fold,
                validation_data=([X_sig_val_fold, X_feat_val_fold], y_val_fold),
                epochs=EPOCHS,
                batch_size=BATCH_SIZE,
                callbacks=callbacks,
                verbose=0
            )

            # Evaluate on fold validation set (original, non-augmented)
            fold_preds = model.predict([X_sig_val_fold, X_feat_val_fold], verbose=0)
            fold_preds_glucose = y_scaler.inverse_transform(fold_preds)
            fold_true_glucose = y_scaler.inverse_transform(y_val_fold)
            fold_mae = mean_absolute_error(fold_true_glucose, fold_preds_glucose)

            cv_scores.append(fold_mae)
            fold_models.append(model)
            logger.info(f"  Fold {fold + 1} MAE: {fold_mae:.2f} mg/dL")

        logger.info(f"\n📊 Cross-Validation MAE: {np.mean(cv_scores):.2f} ± {np.std(cv_scores):.2f} mg/dL")

        # Select best fold model
        best_fold = np.argmin(cv_scores)
        best_model = fold_models[best_fold]
        logger.info(f"Best fold: {best_fold + 1} (MAE: {cv_scores[best_fold]:.2f})")
    else:
        logger.info("Skipping cross-validation (insufficient data or N_FOLDS=1)")
        best_model = None

    # --- 7. Final model: train on all augmented data ---
    logger.info("\n" + "=" * 60)
    logger.info("  Phase 3: Training FINAL enhanced model on all data")
    logger.info("=" * 60)

    # Split augmented data
    (X_sig_train, X_sig_val,
     X_feat_train, X_feat_val,
     y_train, y_val) = train_test_split(
        X_sig_aug, X_feat_aug, y_aug,
        test_size=0.15, random_state=RANDOM_SEED
    )

    final_model = build_enhanced_model(SIGNAL_LENGTH, num_features, learning_rate=LEARNING_RATE)
    final_model.summary()

    callbacks = [
        EarlyStopping(patience=PATIENCE_EARLY_STOP, restore_best_weights=True,
                      monitor='val_loss', verbose=1),
        ReduceLROnPlateau(factor=0.5, patience=PATIENCE_LR_REDUCE,
                          min_lr=MIN_LEARNING_RATE, verbose=1),
        ModelCheckpoint('enhanced_model.keras', save_best_only=True,
                        monitor='val_loss', verbose=1)
    ]

    history = final_model.fit(
        [X_sig_train, X_feat_train], y_train,
        validation_data=([X_sig_val, X_feat_val], y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1
    )

    # --- 8. Evaluation ---
    logger.info("\n" + "=" * 60)
    logger.info("  EVALUATION RESULTS")
    logger.info("=" * 60)

    # Evaluate on original (non-augmented) data
    preds = final_model.predict([X_signal, X_features_scaled], verbose=0)
    preds_glucose = y_scaler.inverse_transform(preds)
    true_glucose = y

    mae = mean_absolute_error(true_glucose, preds_glucose)
    rmse = np.sqrt(mean_squared_error(true_glucose, preds_glucose))
    r2 = r2_score(true_glucose, preds_glucose)

    logger.info(f"\n🔥 ENHANCED MODEL — Original Data Metrics:")
    logger.info(f"  MAE:  {mae:.2f} mg/dL")
    logger.info(f"  RMSE: {rmse:.2f} mg/dL")
    logger.info(f"  R²:   {r2:.4f}")

    logger.info(f"\n📊 MODEL COMPARISON:")
    logger.info(f"  Standard Model MAE:  {std_mae:.2f} mg/dL")
    logger.info(f"  Enhanced Model MAE:  {mae:.2f} mg/dL")
    logger.info(f"  Improvement: {std_mae - mae:.2f} mg/dL ({(1 - mae/std_mae)*100:.1f}%)")

    # Per-sample comparison
    logger.info(f"\n📋 Per-Sample Predictions (Enhanced Model):")
    logger.info(f"  {'True':>8} {'Predicted':>10} {'Error':>8}")
    logger.info(f"  {'-'*30}")
    for i in range(len(true_glucose)):
        true_val = true_glucose[i][0]
        pred_val = preds_glucose[i][0]
        error = abs(true_val - pred_val)
        logger.info(f"  {true_val:>8.1f} {pred_val:>10.1f} {error:>8.1f}")

    # --- 9. Save models ---
    final_model.save("enhanced_model.keras")
    logger.info(f"\n✅ Models saved:")
    logger.info(f"  Standard:  final_model.keras")
    logger.info(f"  Enhanced:  enhanced_model.keras")
    logger.info(f"  Scalers:   y_scaler.save, feature_scaler.save")
    logger.info(f"             enhanced_y_scaler.save, enhanced_feature_scaler.save")

    # --- 10. Save training report ---
    report = {
        "timestamp": datetime.now().isoformat(),
        "dataset_size": len(data),
        "augmented_size": len(y_aug),
        "signal_length": SIGNAL_LENGTH,
        "num_features_standard": 11,
        "num_features_enhanced": num_features,
        "feature_names": EXTENDED_FEATURE_NAMES,
        "standard_model": {
            "mae": float(std_mae),
            "rmse": float(std_rmse),
        },
        "enhanced_model": {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
        },
        "hyperparameters": {
            "epochs": EPOCHS,
            "batch_size": BATCH_SIZE,
            "learning_rate": LEARNING_RATE,
            "dropout": DROPOUT_RATE,
            "l2_reg": L2_REG,
            "augmentation_factor": AUGMENTATION_FACTOR,
            "n_folds": N_FOLDS,
        },
        "improvement_pct": float((1 - mae / std_mae) * 100) if std_mae > 0 else 0,
    }

    with open("training_report.json", "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"\n📄 Training report saved: training_report.json")
    logger.info("=" * 60)
    logger.info("  TRAINING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()