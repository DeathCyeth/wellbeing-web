// API Service - Handles all backend communication
// Uses relative /api when frontend is served from same host (e.g. deployed); else localhost for local dev
function getApiBaseUrl() {
    if (typeof window === 'undefined') return 'http://localhost:8000/api';
    if (window.API_BASE_URL) return window.API_BASE_URL;
    var isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (isLocal && window.location.port !== '8000') return 'http://localhost:8000/api';
    return '/api';
}
const API_BASE_URL = getApiBaseUrl();

// COMMON API ENDPOINT VARIATIONS:
// If the endpoints below don't work, try uncommenting and modifying these alternatives:
// 
// Login alternatives:
//   '/login' instead of '/users/login'
//   '/auth/login' instead of '/users/login'
//   '/api/login' instead of '/api/users/login'
//
// Registration alternatives:
//   '/register' instead of '/users'
//   '/auth/register' instead of '/users'
//   '/api/register' instead of '/api/users'
//
// To test: Open browser console (F12) and check the "API Request" and "API Response" logs

class ApiService {
    constructor() {
        this.baseUrl = API_BASE_URL;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        // Convert body to JSON string if it's an object
        if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
            config.body = JSON.stringify(config.body);
        }

        try {
            console.log('API Request:', url, config);
            
            // Add timeout to prevent hanging
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Request timeout - server took too long to respond')), 10000);
            });
            
            const fetchPromise = fetch(url, config);
            const response = await Promise.race([fetchPromise, timeoutPromise]);
            
            // Check if response has content
            const contentType = response.headers.get('content-type');
            let data;
            
            if (contentType && contentType.includes('application/json')) {
                const text = await response.text();
                console.log('API Response:', text);
                try {
                    data = JSON.parse(text);
                } catch (e) {
                    throw new Error(`Invalid JSON response: ${text}`);
                }
            } else {
                const text = await response.text();
                console.log('API Response (non-JSON):', text);
                data = { message: text };
            }
            
            if (!response.ok) {
                const errorMsg = data.error || data.message || data.detail || `HTTP error! status: ${response.status}`;
                console.error('API Error:', errorMsg, data);
                const error = new Error(errorMsg);
                error.response = data;
                error.status = response.status;
                throw error;
            }
            
            return data;
        } catch (error) {
            console.error('API request failed:', error);
            
            // Handle different types of errors
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error(`Cannot connect to server. Please check:\n1. Is your backend server running?\n2. Is the API URL correct? (Currently: ${this.baseUrl})\n3. Check browser console for CORS errors`);
            }
            
            if (error.message) {
                throw error;
            }
            throw new Error(`Network error: ${error.message || 'Unable to connect to server'}`);
        }
    }

    // Initialize connection (optional - can be used to check server availability)
    async init() {
        try {
            // Try health endpoint first
            try {
                await this.request('/health');
                return true;
            } catch (e) {
                // If health endpoint doesn't exist, try a simple GET to root
                try {
                    await fetch(`${this.baseUrl}/`, { method: 'GET' });
                    return true;
                } catch (e2) {
                    console.warn('Server connection check failed. This is OK if your server doesn\'t have a health endpoint.');
                    // Don't fail initialization - let actual requests handle errors
                    return true;
                }
            }
        } catch (error) {
            console.warn('Server connection failed:', error);
            return false;
        }
    }
    
    // Test connection to a specific endpoint
    async testConnection() {
        const testEndpoints = ['/health', '/', '/users'];
        for (const endpoint of testEndpoints) {
            try {
                const response = await fetch(`${this.baseUrl}${endpoint}`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                if (response.status !== 404) {
                    return { success: true, endpoint, status: response.status };
                }
            } catch (e) {
                continue;
            }
        }
        return { success: false, message: 'Cannot reach server. Check if backend is running and API URL is correct.' };
    }

    // User authentication
    async getUser(username, password) {
        try {
            const response = await this.request('/users/login', {
                method: 'POST',
                body: { username, password },
            });
            // Handle different response formats
            if (response.user) return response.user;
            if (response.username) return response;
            return response;
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    }

    async createUser(userData) {
        try {
            const response = await this.request('/users', {
                method: 'POST',
                body: userData,
            });
            return response;
        } catch (error) {
            console.error('Registration error:', error);
            // Check if it's a duplicate username error
            if (error.message && (error.message.includes('already') || error.message.includes('taken') || error.message.includes('exists'))) {
                throw new Error('Username already taken');
            }
            throw error;
        }
    }

    async getUserByUsername(username) {
        return await this.request(`/users/${username}`);
    }

    async getUserByPatientId(patientId) {
        return await this.request(`/users/by-patient-id/${patientId}`);
    }

    /** List all patients for dropdown: [{ username, name, patient_id }] */
    async getPatients() {
        try {
            return await this.request('/users/patients');
        } catch (error) {
            console.warn('Could not load patient list:', error);
            return [];
        }
    }

    async updateUser(username, name, age = null, sex = null) {
        return await this.request(`/users/${username}`, {
            method: 'PUT',
            body: { name, age, sex },
        });
    }

    // Preferences (Likes/Dislikes)
    async getLikesDislikes(username) {
        try {
            return await this.request(`/users/${username}/preferences`);
        } catch (error) {
            return { likes: '', dislikes: '' };
        }
    }

    async getLikesDislikesByPatientId(patientId) {
        try {
            return await this.request(`/users/by-patient-id/${patientId}/preferences`);
        } catch (error) {
            return { likes: '', dislikes: '' };
        }
    }

    async upsertLikesDislikes(username, likes, dislikes) {
        return await this.request(`/users/${username}/preferences`, {
            method: 'POST',
            body: { likes, dislikes },
        });
    }

    // Doctor Notes
    async getDoctorNotes(username) {
        try {
            return await this.request(`/users/${username}/notes`);
        } catch (error) {
            return [];
        }
    }

    async getDoctorNotesByPatientId(patientId) {
        try {
            return await this.request(`/users/by-patient-id/${patientId}/notes`);
        } catch (error) {
            return [];
        }
    }

    async getDoctorNotesSummary(username) {
        try {
            return await this.request(`/users/${username}/notes/summary`);
        } catch (error) {
            return { summary: "No notes available.", total_notes: 0 };
        }
    }

    async getDoctorNotesSummaryByPatientId(patientId) {
        try {
            return await this.request(`/users/by-patient-id/${patientId}/notes/summary`);
        } catch (error) {
            return { summary: "No notes available.", total_notes: 0 };
        }
    }

    async addDoctorNote(username, note) {
        return await this.request(`/users/${username}/notes`, {
            method: 'POST',
            body: { note },
        });
    }

    async getMedicalInfo(username) {
        try {
            return await this.request(`/users/${username}/medical-info`);
        } catch (error) {
            return {
                past_medical_history: "",
                patient_goals: "",
                food_allergies: "",
                physical_activity: "",
                current_medications: "",
                height: "",
                weight: "",
                sex: ""
            };
        }
    }

    async getMedicalInfoByPatientId(patientId) {
        try {
            return await this.request(`/users/by-patient-id/${patientId}/medical-info`);
        } catch (error) {
            return {
                past_medical_history: "",
                patient_goals: "",
                food_allergies: "",
                physical_activity: "",
                current_medications: "",
                height: "",
                weight: "",
                sex: ""
            };
        }
    }

    async updateMedicalInfo(username, medicalInfo) {
        return await this.request(`/users/${username}/medical-info`, {
            method: 'POST',
            body: medicalInfo,
        });
    }

    // AI Companion with conversation history (medicalInfo = doctor-recorded data; image = optional base64/data URL for current message)
    // role = 'doctor' and patient_context for doctor-side AI
    async getAIAdvice(question, userName, likes, dislikes, notes, conversationHistory = [], medicalInfo = {}, image = null, role = null, patientContext = '', contextUsername = '') {
        const body = {
            question,
            user_name: userName || 'User',
            likes: likes || '',
            dislikes: dislikes || '',
            notes: notes || [],
            medical_info: medicalInfo || {},
            conversation_history: conversationHistory
        };
        if (image) body.image = image;
        if (role) body.role = role;
        if (patientContext) body.patient_context = patientContext;
        if (contextUsername) body.context_username = contextUsername;
        return await this.request('/ai/advice', { method: 'POST', body });
    }

    /** Curated PubMed PMIDs: global + optional patient_username for patient-scoped rows */
    async getLiterature(patientUsername) {
        const q = patientUsername ? `?patient_username=${encodeURIComponent(patientUsername)}` : '';
        return await this.request('/literature' + q);
    }

    async addLiterature(payload) {
        return await this.request('/literature', { method: 'POST', body: payload });
    }

    async deleteLiterature(id) {
        return await this.request('/literature/' + id, { method: 'DELETE' });
    }

    /** Submit in-app feedback (server verifies password). */
    async submitFeedback({ username, password, message, source }) {
        return await this.request('/feedback', {
            method: 'POST',
            body: { username, password, message, source: source || 'app' },
        });
    }

    /** Admin: list feedback (requires FEEDBACK_ADMIN_USERNAMES or role Admin). */
    async listFeedbackAdmin({ username, password }) {
        return await this.request('/feedback/admin/list', {
            method: 'POST',
            body: { username, password },
        });
    }

    /** Create Admin user (requires ADMIN_BOOTSTRAP_KEY on server). */
    async createAdminBootstrap({ bootstrap_key, username, password, name }) {
        return await this.request('/admin/bootstrap', {
            method: 'POST',
            body: { bootstrap_key, username, password, name },
        });
    }

    // Generate personalized nutrition plan for a patient (username or patient_id)
    async generateNutritionPlan(params) {
        return await this.request('/ai/nutrition-plan', {
            method: 'POST',
            body: typeof params === 'string' ? { username: params } : params
        });
    }
}

// Create singleton instance
const apiService = new ApiService();

