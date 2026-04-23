user_offsets = {}

def calibrate_user(user_id, predicted, actual):
    user_offsets[user_id] = actual - predicted

def apply_calibration(user_id, prediction):
    return prediction + user_offsets.get(user_id, 0)