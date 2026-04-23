const BASE_URL = 'http://localhost:5000';

export const api = {
  signup: async (email, password) => {
    const res = await fetch(`${BASE_URL}/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return res.json();
  },

  login: async (email, password) => {
    const res = await fetch(`${BASE_URL}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return res.json();
  },

  predict: async (videoFile) => {
    const formData = new FormData();
    formData.append('video', videoFile);
    const res = await fetch(`${BASE_URL}/predict`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },
};