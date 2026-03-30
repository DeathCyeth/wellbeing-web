// Main Application Logic

// Current user state
let currentUser = null;

// AI Conversation history - stores conversation for current session
let aiConversationHistory = [];
// Doctor AI Assistant conversation history
let doctorAIConversationHistory = [];

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    console.log('Initializing app...');
    
    // Check if user is already logged in (from localStorage)
    const savedUser = localStorage.getItem('currentUser');
    if (savedUser) {
        try {
            currentUser = JSON.parse(savedUser);
            console.log('Found saved user:', currentUser);
            showUserHome();
        } catch (e) {
            console.error('Error parsing saved user:', e);
            localStorage.removeItem('currentUser');
            showScreen('loginScreen');
        }
    } else {
        // Support #register so QR code / link can open registration directly
        if (window.location.hash === '#register') {
            showScreen('registerScreen');
        } else {
            showScreen('loginScreen');
        }
    }

    // Initialize API connection (non-blocking)
    apiService.init().catch(error => {
        console.warn('Server connection check:', error);
    });

    // Setup event listeners
    console.log('Setting up event listeners...');
    setupEventListeners();
    
    // Add connection test button to login screen
    addConnectionTestButton();
    // If user lands with #register, show register screen (e.g. from QR scan)
    window.addEventListener('hashchange', function () {
        if (!currentUser && window.location.hash === '#register') showScreen('registerScreen');
    });
    console.log('App initialization complete');
}

function addConnectionTestButton() {
    const loginForm = document.getElementById('loginForm');
    const testBtn = document.createElement('button');
    testBtn.type = 'button';
    testBtn.className = 'btn btn-link';
    testBtn.textContent = 'Test Server Connection';
    testBtn.style.fontSize = '0.85rem';
    testBtn.style.marginTop = '10px';
    testBtn.onclick = async function() {
        testBtn.disabled = true;
        testBtn.textContent = 'Testing...';
        try {
            const result = await apiService.testConnection();
            if (result.success) {
                showToast(`âœ“ Server connection successful! (${result.endpoint})`, 'success');
            } else {
                showToast(`âœ— ${result.message}`, 'error');
            }
        } catch (error) {
            showToast(`âœ— Connection failed: ${error.message}`, 'error');
        } finally {
            testBtn.disabled = false;
            testBtn.textContent = 'Test Server Connection';
        }
    };
    
    // Insert before the error message div
    const errorDiv = document.getElementById('loginError');
    loginForm.insertBefore(testBtn, errorDiv);
}

function setupEventListeners() {
    // Login form
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleLogin();
    });

    // Register form
    document.getElementById('registerForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleRegister();
    });

    // Patient preferences form
    document.getElementById('patientPrefsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await savePatientPreferences();
    });

    // Doctor update patient form
    document.getElementById('doctorUpdatePatientForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await updatePatientInfo();
    });

    // Doctor add note form
    document.getElementById('doctorAddNoteForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await addDoctorNote();
    });

    // Patient account form
    document.getElementById('patientAccountForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await savePatientAccount();
    });

    // Doctor medical info forms
    document.getElementById('doctorBiometricForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveDoctorMedicalInfo('biometric');
    });

    document.getElementById('doctorMedicalHistoryForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveDoctorMedicalInfo('medical_history');
    });

    document.getElementById('doctorPatientGoalsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveDoctorMedicalInfo('goals');
    });

    document.getElementById('doctorFoodAllergiesForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveDoctorMedicalInfo('allergies');
    });

    document.getElementById('doctorPhysicalActivityForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveDoctorMedicalInfo('activity');
    });

    document.getElementById('doctorMedicationsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveDoctorMedicalInfo('medications');
    });

    // AI form - attach event listener (only one should exist now)
    const aiForm = document.getElementById('aiForm');
    if (aiForm) {
        aiForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            console.log('AI form submitted');
            await getAIAdvice();
        });
        console.log('AI form event listener attached');
    } else {
        console.error('AI form not found during initialization');
    }

    // AI image attach: click label opens file input
    const aiImageAttachBtn = document.getElementById('aiImageAttachBtn');
    const aiImageInput = document.getElementById('aiImageInput');
    if (aiImageAttachBtn && aiImageInput) {
        aiImageAttachBtn.addEventListener('click', () => aiImageInput.click());
    }
    if (aiImageInput) {
        aiImageInput.addEventListener('change', function () {
            const nameEl = document.getElementById('aiImageName');
            const removeBtn = document.getElementById('aiImageRemoveBtn');
            if (this.files && this.files.length > 0) {
                if (nameEl) nameEl.textContent = this.files[0].name;
                if (removeBtn) removeBtn.style.display = 'inline';
            } else {
                if (nameEl) nameEl.textContent = '';
                if (removeBtn) removeBtn.style.display = 'none';
            }
        });
    }
    const aiImageRemoveBtn = document.getElementById('aiImageRemoveBtn');
    if (aiImageRemoveBtn && aiImageInput) {
        aiImageRemoveBtn.addEventListener('click', () => {
            aiImageInput.value = '';
            const nameEl = document.getElementById('aiImageName');
            if (nameEl) nameEl.textContent = '';
            aiImageRemoveBtn.style.display = 'none';
        });
    }

    // Doctor: Generate Nutrition Plan button
    const doctorGeneratePlanBtn = document.getElementById('doctorGeneratePlanBtn');
    if (doctorGeneratePlanBtn) {
        doctorGeneratePlanBtn.addEventListener('click', () => generateDoctorNutritionPlan());
    }
    // Doctor: AI Assistant Send button
    const doctorAISendBtn = document.getElementById('doctorAISendBtn');
    if (doctorAISendBtn) {
        doctorAISendBtn.addEventListener('click', () => sendDoctorAIMessage());
    }
    // Doctor: Print Nutrition Plan
    const doctorNutritionPlanPrintBtn = document.getElementById('doctorNutritionPlanPrintBtn');
    if (doctorNutritionPlanPrintBtn) {
        doctorNutritionPlanPrintBtn.addEventListener('click', () => printNutritionPlan());
    }
    // Doctor: BMI/BMR Calculate button
    const doctorBMICalculateBtn = document.getElementById('doctorBMICalculateBtn');
    if (doctorBMICalculateBtn) {
        doctorBMICalculateBtn.addEventListener('click', () => updateDoctorBMICalculator());
    }
}

// Toggle collapsible sections
function toggleCollapsible(id) {
    const content = document.getElementById(`${id}-content`);
    const icon = document.getElementById(`${id}-icon`);
    const header = icon.closest('.collapsible-header');
    
    if (content.style.display === 'none' || !content.style.display) {
        content.style.display = 'block';
        icon.textContent = '▲';
        header.classList.add('active');
    } else {
        content.style.display = 'none';
        icon.textContent = '▼';
        header.classList.remove('active');
    }
}

function refreshLoginHealthHints() {
    var hintEl = document.getElementById('loginSiteHint');
    var warnEl = document.getElementById('loginPersistenceWarning');
    if (warnEl) {
        warnEl.style.display = 'none';
        warnEl.textContent = '';
    }
    if (!hintEl || typeof apiService === 'undefined') return;
    hintEl.textContent = "You're on: " + (window.location.hostname || window.location.host || '');
    apiService.request('/health').then(function (r) {
        if (r && r.instance_id && hintEl) hintEl.textContent = "You're on: " + (window.location.hostname || '') + " \u00B7 Server: " + r.instance_id;
        if (r && r.ephemeral_data_warning && warnEl) {
            warnEl.style.display = 'block';
            warnEl.textContent = 'Server is using temporary database storage: user accounts and records can be reset when the host redeploys. Ask your admin to add PostgreSQL (DATABASE_URL on Render) or a persistent disk with SQLITE_DATABASE_PATH. This is not caused by app updates alone.';
        }
    }).catch(function () {});
}

// Screen navigation
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
    // When showing login screen, clear any previous error and refresh "You're on:" + server instance ID
    if (screenId === 'loginScreen') {
        var errEl = document.getElementById('loginError');
        if (errEl) errEl.textContent = '';
        refreshLoginHealthHints();
    }
}

// Login handler
async function handleLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');

    errorDiv.textContent = '';

    if (!username || !password) {
        errorDiv.textContent = 'Please enter username and password.';
        return;
    }

    try {
        console.log('Attempting login for:', username);
        const user = await apiService.getUser(username, password);
        console.log('Login response:', user);
        
        if (!user) {
            errorDiv.textContent = 'Invalid username or password.';
            return;
        }

        // Handle different response formats
        const userData = {
            username: user.username || username,
            name: user.name || user.full_name || '',
            role: user.role || 'Patient',
            patient_id: user.patient_id || '',
            age: user.age || null
        };

        if (!userData.username) {
            errorDiv.textContent = 'Invalid response from server. Please check the console.';
            return;
        }

        currentUser = userData;
        localStorage.setItem('currentUser', JSON.stringify(currentUser));
        showUserHome();
    } catch (error) {
        let errorMessage = error.message || 'Invalid username or password.';
        
        // Provide more helpful error messages for connection issues
        if (errorMessage.includes('Cannot connect to server') || errorMessage.includes('fetch')) {
            errorMessage = 'Cannot connect to server. Please check:\n1. Is your backend server running?\n2. Is the API URL correct in api-service.js?\n3. Check browser console (F12) for details.';
            errorDiv.style.whiteSpace = 'pre-line';
        } else if (errorMessage.toLowerCase().includes('invalid') && (errorMessage.includes('username') || errorMessage.includes('password'))) {
            errorMessage = 'Invalid username or password.\n\nOn a tablet or other device? Use the exact same web address as on your computer (see "You\'re on:" below). Type your username and password again—no extra spaces. If you just created this account on another device, wait a moment and try again.';
            errorDiv.style.whiteSpace = 'pre-line';
        }
        
        errorDiv.textContent = errorMessage;
        console.error('Login error details:', error);
        showToast('Login failed. See message above.', 'error');
    }
}

// Register handler
async function handleRegister() {
    const username = document.getElementById('registerUsername').value.trim();
    const name = document.getElementById('registerName').value.trim();
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = document.getElementById('registerConfirmPassword').value;
    const role = document.getElementById('registerRole').value;
    const errorDiv = document.getElementById('registerError');

    errorDiv.textContent = '';

    if (!username || !name || !password || !confirmPassword) {
        errorDiv.textContent = 'Please fill in all fields.';
        return;
    }

    if (password !== confirmPassword) {
        errorDiv.textContent = 'Passwords do not match.';
        return;
    }

    try {
        console.log('Attempting registration for:', username);
        const response = await apiService.createUser({
            username,
            password,
            name,
            role
        });
        console.log('Registration response:', response);

        // Show patient ID if it was returned (for patients)
        if (response.patient_id && role === 'Patient') {
            showToast(`Registration successful! Your Patient ID is: ${response.patient_id}. Please log in.`, 'success');
        } else {
            showToast('Registration successful! Please log in.', 'success');
        }
        showScreen('loginScreen');
        // Clear form
        document.getElementById('registerForm').reset();
        errorDiv.textContent = '';
    } catch (error) {
        let errorMessage = error.message || 'Registration failed. Please try again.';
        
        // Provide more helpful error messages for connection issues
        if (errorMessage.includes('Cannot connect to server') || errorMessage.includes('fetch')) {
            errorMessage = 'Cannot connect to server. Please check:\n1. Is your backend server running?\n2. Is the API URL correct in api-service.js?\n3. Check browser console (F12) for details.';
            errorDiv.style.whiteSpace = 'pre-line';
        }
        
        errorDiv.textContent = errorMessage;
        console.error('Registration error details:', error);
        showToast(`Registration failed: ${errorMessage.split('\n')[0]}`, 'error');
    }
}

// Show user home based on role
function showUserHome() {
    if (!currentUser) {
        showScreen('loginScreen');
        return;
    }

    if (currentUser.role.toLowerCase() === 'patient') {
        showPatientHome();
    } else {
        showDoctorHome();
    }
}

// Patient Home
async function showPatientHome() {
    console.log('Showing patient home for:', currentUser);
    showScreen('patientHome');
    
    const welcomeEl = document.getElementById('patientWelcome');
    if (welcomeEl) {
        welcomeEl.textContent = `Welcome, ${currentUser.name}`;
    }

    // Display Patient ID under name
    await displayPatientIdInHeader();

    // Verify tabs are present
    const tabsEl = document.querySelector('.patient-nav-tabs');
    if (!tabsEl) {
        console.error('ERROR: Patient navigation tabs not found in HTML!');
        alert('ERROR: Patient tabs not found. Please refresh the page or check if index.html has been updated correctly.');
        return;
    }
    
    console.log('Patient tabs verified, showing main tab...');
    
    // Show main tab by default
    showPatientTab('main');

    // Load account information
    await loadPatientAccount();
    
    // Clear AI response but keep conversation history
    const aiResponseEl = document.getElementById('aiResponse');
    const aiQuestionEl = document.getElementById('aiQuestion');
    if (aiResponseEl) {
        aiResponseEl.innerHTML = '<p class="ai-placeholder">AI response will appear here...</p>';
    }
    if (aiQuestionEl) {
        aiQuestionEl.value = '';
    }
    
    // AI form should already have event listener from setupEventListeners
    // No need to re-attach it here to avoid duplicates
    
    // Initialize conversation history if needed (keep existing if already started)
    if (aiConversationHistory.length === 0) {
        // Will be initialized when first AI call is made
    }
}

// Patient Tab Navigation - Make it globally accessible
window.showPatientTab = function showPatientTab(tabName) {
    console.log('Switching to tab:', tabName);
    
    // Hide all tab contents
    document.querySelectorAll('.patient-tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab content
    const selectedTab = document.getElementById(`patientTab-${tabName}`);
    if (selectedTab) {
        selectedTab.classList.add('active');
        console.log('Tab content shown:', selectedTab.id);
    } else {
        console.error('Tab content not found:', `patientTab-${tabName}`);
    }
    
    // Add active class to selected tab button
    const selectedTabButton = document.getElementById(`tab-${tabName}`);
    if (selectedTabButton) {
        selectedTabButton.classList.add('active');
        console.log('Tab button activated:', selectedTabButton.id);
    } else {
        console.error('Tab button not found:', `tab-${tabName}`);
    }
    
    // Load data for account tab when switching to it (refresh so notes are up to date)
    if (tabName === 'account') {
        loadPatientAccount();
    }
}

async function displayPatientIdInHeader() {
    // Load patient ID and display in header
    console.log('displayPatientIdInHeader called, currentUser:', currentUser);
    
    try {
        // Always fetch fresh patient ID from server
        const user = await apiService.getUserByUsername(currentUser.username);
        console.log('Fetched user data:', user);
        
        if (user && user.patient_id) {
            currentUser.patient_id = user.patient_id;
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            console.log('Patient ID set to:', currentUser.patient_id);
        } else {
            console.warn('No patient_id found for user:', user);
        }
        
        const patientIdHeader = document.getElementById('patientIdHeader');
        const patientIdHeaderValue = document.getElementById('patientIdHeaderValue');
        
        console.log('Header elements found:', {
            header: !!patientIdHeader,
            value: !!patientIdHeaderValue,
            patientId: currentUser.patient_id
        });
        
        if (patientIdHeader && patientIdHeaderValue) {
            if (currentUser.patient_id) {
                patientIdHeaderValue.textContent = currentUser.patient_id;
                patientIdHeader.style.display = 'flex';
                console.log('Patient ID displayed:', currentUser.patient_id);
            } else {
                patientIdHeader.style.display = 'none';
                console.warn('No patient ID to display');
            }
        } else {
            console.error('Patient ID header elements not found in DOM');
        }
    } catch (error) {
        console.error('Error loading patient ID:', error);
    }
}

async function loadPatientAccount() {
    // Load user info
    try {
        const user = await apiService.getUserByUsername(currentUser.username);
        if (user) {
            currentUser.name = user.name || currentUser.name;
            currentUser.age = user.age || null;
            currentUser.patient_id = user.patient_id || currentUser.patient_id;
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            
            // Update patient ID display immediately if we have it
            const patientIdValue = document.getElementById('patientIdValueAccount');
            if (patientIdValue && currentUser.patient_id) {
                patientIdValue.textContent = currentUser.patient_id;
            }
            
            // Update header display
            await displayPatientIdInHeader();
        }
    } catch (error) {
        console.error('Error loading user info:', error);
    }
    
    // Display patient ID (will fetch if not already loaded)
    displayPatientIdAccount();
    
    // Load name and age
    const nameEl = document.getElementById('patientName');
    const ageEl = document.getElementById('patientAge');
    if (nameEl) nameEl.value = currentUser.name || '';
    if (ageEl) ageEl.value = currentUser.age || '';
    
    // Load preferences
    try {
        const prefs = await apiService.getLikesDislikes(currentUser.username);
        const likesEl = document.getElementById('patientLikes');
        const dislikesEl = document.getElementById('patientDislikes');
        if (likesEl) likesEl.value = prefs.likes || '';
        if (dislikesEl) dislikesEl.value = prefs.dislikes || '';
    } catch (error) {
        console.error('Error loading preferences:', error);
    }

    // Load notes summary
    await loadPatientNotesSummary();
}

async function savePatientAccount() {
    const name = document.getElementById('patientName').value.trim();
    const age = document.getElementById('patientAge').value;
    
    if (!name) {
        showToast('Please enter your name', 'error');
        return;
    }
    
    try {
        const ageValue = age ? parseInt(age) : null;
        await apiService.updateUser(currentUser.username, name, ageValue);
        currentUser.name = name;
        currentUser.age = ageValue;
        localStorage.setItem('currentUser', JSON.stringify(currentUser));
        showToast('Account information saved', 'success');
    } catch (error) {
        showToast('Error saving account information', 'error');
        console.error('Error saving account:', error);
    }
}

function displayPatientIdAccount() {
    const patientIdValue = document.getElementById('patientIdValueAccount');
    
    if (patientIdValue) {
        if (currentUser && currentUser.patient_id) {
            patientIdValue.textContent = currentUser.patient_id;
            console.log('Patient ID displayed:', currentUser.patient_id);
        } else {
            // Show loading state
            patientIdValue.textContent = 'Loading...';
            // Try to fetch patient_id if not in currentUser
            fetchPatientIdAccount();
        }
    } else {
        console.error('Patient ID value element not found');
    }
}

async function fetchPatientIdAccount() {
    try {
        const user = await apiService.getUserByUsername(currentUser.username);
        if (user && user.patient_id) {
            currentUser.patient_id = user.patient_id;
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            const patientIdValue = document.getElementById('patientIdValueAccount');
            if (patientIdValue) {
                patientIdValue.textContent = user.patient_id;
            }
        } else {
            const patientIdValue = document.getElementById('patientIdValueAccount');
            if (patientIdValue) {
                patientIdValue.textContent = 'Not available';
            }
        }
    } catch (error) {
        console.error('Error fetching patient ID:', error);
        const patientIdValue = document.getElementById('patientIdValueAccount');
        if (patientIdValue) {
            patientIdValue.textContent = 'Error loading';
        }
    }
}

function copyPatientIdAccount() {
    const patientIdValue = document.getElementById('patientIdValueAccount');
    if (patientIdValue) {
        const text = patientIdValue.textContent;
        if (text && text !== 'Loading...' && text !== 'Not available' && text !== 'Error loading') {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Patient ID copied to clipboard!', 'success');
            }).catch(err => {
                console.error('Failed to copy:', err);
                showToast('Failed to copy. Please select and copy manually.', 'error');
            });
        }
    }
}

function copyPatientIdFromHeader() {
    if (currentUser && currentUser.patient_id) {
        navigator.clipboard.writeText(currentUser.patient_id).then(() => {
            showToast('Patient ID copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            showToast('Failed to copy. Please select and copy manually.', 'error');
        });
    }
}

// Generate a formatted summary of all doctor inputs (medical info + preferences). Set showAll to true to list every category even when empty.
function generateMedicalSummary(user, medicalInfo, prefs, showAll) {
    const parts = [];
    const empty = '<span style="color: var(--text-light); font-style: italic;">—</span>';

    if (!medicalInfo || typeof medicalInfo !== 'object') medicalInfo = {};
    if (!prefs || typeof prefs !== 'object') prefs = { likes: '', dislikes: '' };

    // Basic Information (doctor can set name, age, sex)
    if (user && (showAll || user.name || user.age || user.sex)) {
        parts.push('<div style="margin-bottom: 15px;"><strong style="color: var(--primary-color);">Basic information</strong>');
        parts.push(`<br>• Name: ${user && user.name ? escapeHtml(user.name) : empty}`);
        parts.push(`<br>• Age: ${user && user.age != null && user.age !== '' ? escapeHtml(String(user.age)) : empty}`);
        parts.push(`<br>• Sex: ${user && user.sex ? escapeHtml(user.sex) : empty}`);
        parts.push('</div>');
    }

    // Biometric Data
    const heightDisplay = (medicalInfo.height_feet != null || medicalInfo.height_inches != null)
        ? [medicalInfo.height_feet != null ? medicalInfo.height_feet + ' ft' : '', medicalInfo.height_inches != null ? medicalInfo.height_inches + ' in' : ''].filter(Boolean).join(' ')
        : (medicalInfo.height || '');
    if (showAll || heightDisplay || medicalInfo.weight) {
        parts.push('<div style="margin-bottom: 15px;"><strong style="color: var(--primary-color);">Biometric data</strong>');
        parts.push(`<br>• Height: ${heightDisplay ? escapeHtml(heightDisplay) : empty}`);
        parts.push(`<br>• Weight: ${medicalInfo.weight ? escapeHtml(medicalInfo.weight) : empty}`);
        parts.push('</div>');
    }

    // Past Medical History
    if (showAll || medicalInfo.past_medical_history) {
        parts.push('<div style="margin-bottom: 15px;"><strong style="color: var(--primary-color);">Past medical history</strong><br>');
        parts.push(medicalInfo.past_medical_history ? escapeHtml(medicalInfo.past_medical_history).replace(/\n/g, '<br>') : empty);
        parts.push('</div>');
    }

    // Patient Goals
    if (showAll || medicalInfo.patient_goals) {
        parts.push('<div style="margin-bottom: 15px;"><strong style="color: var(--primary-color);">Patient goals</strong><br>');
        parts.push(medicalInfo.patient_goals ? escapeHtml(medicalInfo.patient_goals).replace(/\n/g, '<br>') : empty);
        parts.push('</div>');
    }

    // Food Allergies
    if (showAll || medicalInfo.food_allergies) {
        parts.push('<div style="margin-bottom: 15px;"><strong style="color: var(--primary-color);">Food allergies</strong><br>');
        parts.push(medicalInfo.food_allergies ? escapeHtml(medicalInfo.food_allergies).replace(/\n/g, '<br>') : empty);
        parts.push('</div>');
    }

    // Physical Activity
    if (showAll || medicalInfo.physical_activity) {
        parts.push('<div style="margin-bottom: 15px;"><strong style="color: var(--primary-color);">Physical activity</strong><br>');
        parts.push(medicalInfo.physical_activity ? escapeHtml(medicalInfo.physical_activity).replace(/\n/g, '<br>') : empty);
        parts.push('</div>');
    }

    // Current Medications
    if (showAll || medicalInfo.current_medications) {
        parts.push('<div style="margin-bottom: 15px;"><strong style="color: var(--primary-color);">Current medications</strong><br>');
        parts.push(medicalInfo.current_medications ? escapeHtml(medicalInfo.current_medications).replace(/\n/g, '<br>') : empty);
        parts.push('</div>');
    }

    // Preferences (likes/dislikes – doctor can edit)
    if (showAll || (prefs && (prefs.likes || prefs.dislikes))) {
        parts.push('<div style="margin-bottom: 15px;"><strong style="color: var(--primary-color);">Preferences</strong>');
        parts.push(`<br>• Likes: ${prefs && prefs.likes ? escapeHtml(prefs.likes) : empty}`);
        parts.push(`<br>• Dislikes: ${prefs && prefs.dislikes ? escapeHtml(prefs.dislikes) : empty}`);
        parts.push('</div>');
    }

    if (parts.length === 0) {
        return '<div style="color: var(--text-light); font-style: italic;">No medical information recorded yet.</div>';
    }
    return parts.join('');
}

// Plain-text patient context for doctor AI (no HTML)
function buildPatientContextText(user, medicalInfo, prefs, notes) {
    if (!user) return '';
    const p = [];
    p.push(`Patient: ${user.name || user.username || ''}`);
    p.push(`Age: ${user.age != null && user.age !== '' ? user.age : 'Not specified'}`);
    if (user.sex) p.push(`Sex: ${user.sex}`);
    const med = medicalInfo || {};
    const heightDisplay = (med.height_feet != null || med.height_inches != null)
        ? [med.height_feet != null ? med.height_feet + ' ft' : '', med.height_inches != null ? med.height_inches + ' in' : ''].filter(Boolean).join(' ')
        : (med.height || '');
    if (heightDisplay) p.push(`Height: ${heightDisplay}`);
    if (med.weight) p.push(`Weight: ${med.weight}`);
    if (med.past_medical_history) p.push(`Past medical history: ${med.past_medical_history}`);
    if (med.patient_goals) p.push(`Goals: ${med.patient_goals}`);
    if (med.food_allergies) p.push(`Food allergies: ${med.food_allergies}`);
    if (med.physical_activity) p.push(`Physical activity: ${med.physical_activity}`);
    if (med.current_medications) p.push(`Medications: ${med.current_medications}`);
    const pr = prefs || {};
    if (pr.likes) p.push(`Likes: ${pr.likes}`);
    if (pr.dislikes) p.push(`Dislikes: ${pr.dislikes}`);
    if (notes && notes.length > 0) {
        p.push('Recent notes: ' + notes.slice(0, 3).map(n => (n.note || '')).join(' | '));
    }
    return p.join('\n');
}

async function loadPatientNotesSummary() {
    const notesDiv = document.getElementById('patientNotes');
    if (!notesDiv) {
        console.error('Patient notes container (#patientNotes) not found.');
        return;
    }
    notesDiv.innerHTML = '<div class="loading">Loading...</div>';

    try {
        // Use same username the doctor uses; also get patient_id for fallback
        let canonicalUsername = currentUser && currentUser.username ? currentUser.username : '';
        let canonicalPatientId = (currentUser && currentUser.patient_id) ? String(currentUser.patient_id).trim() : '';
        let userData = null;
        try {
            userData = await apiService.getUserByUsername(canonicalUsername);
            if (userData) {
                if (userData.username) canonicalUsername = userData.username;
                if (userData.patient_id) canonicalPatientId = String(userData.patient_id).trim();
            }
        } catch (e) {
            console.warn('getUserByUsername failed, using currentUser:', e);
        }

        let medicalInfo = {};
        let prefs = { likes: '', dislikes: '' };
        if (canonicalUsername) {
            const [medByUser, prefsByUser] = await Promise.all([
                apiService.getMedicalInfo(canonicalUsername).catch(() => ({})),
                apiService.getLikesDislikes(canonicalUsername).catch(() => ({ likes: '', dislikes: '' }))
            ]);
            medicalInfo = medByUser || {};
            prefs = prefsByUser || { likes: '', dislikes: '' };
        }
        // If empty and we have patient_id, try by patient_id (doctor may have saved under 816279)
        const medicalInfoEmpty = !Object.values(medicalInfo || {}).some(v => v && String(v).trim());
        const prefsEmpty = !(prefs && ((prefs.likes && prefs.likes.trim()) || (prefs.dislikes && prefs.dislikes.trim())));
        if ((medicalInfoEmpty || prefsEmpty) && canonicalPatientId) {
            if (medicalInfoEmpty) {
                const medById = await apiService.getMedicalInfoByPatientId(canonicalPatientId).catch(() => ({}));
                if (medById && Object.values(medById).some(v => v && String(v).trim())) {
                    medicalInfo = medById;
                }
            }
            if (prefsEmpty) {
                const prefsById = await apiService.getLikesDislikesByPatientId(canonicalPatientId).catch(() => ({ likes: '', dislikes: '' }));
                if (prefsById && ((prefsById.likes && prefsById.likes.trim()) || (prefsById.dislikes && prefsById.dislikes.trim()))) {
                    prefs = prefsById;
                }
            }
        }

        // 1) Fetch notes by username (same API as doctor). 2) If 0 notes, try by Patient ID (e.g. 816279)
        let notes = [];
        let fetchError = null;
        if (canonicalUsername) {
            try {
                notes = await apiService.request('/users/' + encodeURIComponent(canonicalUsername) + '/notes');
                if (!Array.isArray(notes)) notes = [];
            } catch (err) {
                fetchError = err;
                console.error('Patient notes API error (by username):', err);
            }
        }
        if (notes.length === 0 && canonicalPatientId) {
            try {
                const byId = await apiService.request('/users/by-patient-id/' + encodeURIComponent(canonicalPatientId) + '/notes');
                if (Array.isArray(byId) && byId.length > 0) {
                    notes = byId;
                    fetchError = null;
                }
            } catch (err) {
                if (!fetchError) fetchError = err;
                console.error('Patient notes API error (by patient_id):', err);
            }
        }
        if (!canonicalUsername && !canonicalPatientId) {
            fetchError = new Error('No username or Patient ID available for this account.');
        }

        const noteCount = notes.length;

        let html = '';

        // 1) Medical information – all doctor input categories (show all, use "—" when empty)
        const medicalSummary = generateMedicalSummary(
            userData || currentUser || {},
            medicalInfo || {},
            prefs || { likes: '', dislikes: '' },
            true
        );
        html += `
            <div class="medical-summary-card" style="background: #f8f9fa; border-left: 4px solid var(--primary-color); padding: 20px; margin-bottom: 20px; border-radius: 8px;">
                <h4 style="margin: 0 0 12px 0; color: var(--primary-color); font-size: 1rem;">Medical information</h4>
                <p style="margin: 0 0 12px 0; color: var(--text-light); font-size: 0.9rem;">Basic info, biometrics, past medical history, goals, allergies, activity, medications, and preferences your doctor has recorded.</p>
                <div style="line-height: 1.8;">${medicalSummary}</div>
            </div>
        `;

        // 2) Doctor's notes (free-form notes)
        html += `
            <div class="notes-summary" style="margin-top: 20px; padding-top: 16px; border-top: 1px solid #eee;">
                <h4 style="margin: 0 0 12px 0; color: var(--primary-color); font-size: 1rem;">Doctor's notes</h4>
                <div class="summary-header" style="margin-bottom: 12px;">
                    <span style="color: var(--text-light); font-weight: normal;">${noteCount} note${noteCount !== 1 ? 's' : ''}</span>
                    <button type="button" class="btn btn-primary" style="margin-left: 8px; padding: 4px 10px; font-size: 0.85rem;" onclick="loadPatientNotesSummary()">Refresh</button>
                </div>
        `;

        if (fetchError) {
            html += '<div class="empty-state" style="margin-top: 8px; color: #c62828;">Could not load notes: ' + escapeHtml(fetchError.message || String(fetchError)) + '</div>';
        } else if (noteCount > 0) {
            notes.forEach(function (note) {
                const date = note.created_at ? new Date(note.created_at).toLocaleString() : '';
                html += `
                    <div class="note-item" style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid var(--primary-color);">
                        <div class="note-text" style="line-height: 1.6; white-space: pre-wrap;">${escapeHtml(note.note || '').replace(/\n/g, '<br>')}</div>
                        <div class="note-date" style="margin-top: 8px; font-size: 0.85em; color: var(--text-light);">${escapeHtml(date)}</div>
                    </div>
                `;
            });
        } else {
            html += '<div class="empty-state" style="margin-top: 8px;">No doctor notes yet. Your doctor adds notes after loading your account (by your username or Patient ID). If they already added notes, log in with the exact same account they used and open the Account tab again.</div>';
        }
        html += '</div>';

        notesDiv.innerHTML = html;
    } catch (error) {
        notesDiv.innerHTML = '<div class="empty-state">Error loading notes. <button type="button" class="btn btn-primary" style="margin-top: 8px;" onclick="loadPatientNotesSummary()">Try again</button></div>';
        console.error('Error loading patient notes:', error);
    }
}

// Removed - patient ID is now displayed in Account tab

async function savePatientPreferences() {
    const likes = document.getElementById('patientLikes').value;
    const dislikes = document.getElementById('patientDislikes').value;

    try {
        await apiService.upsertLikesDislikes(currentUser.username, likes, dislikes);
        showToast('Preferences saved', 'success');
    } catch (error) {
        showToast('Error saving preferences', 'error');
        console.error('Error saving preferences:', error);
    }
}

// AI Companion with conversation memory - Make it globally accessible
window.getAIAdvice = async function getAIAdvice() {
    const questionInput = document.getElementById('aiQuestion');
    const responseDiv = document.getElementById('aiResponse');
    const submitBtn = document.getElementById('aiSubmitBtn');
    
    if (!questionInput || !responseDiv || !submitBtn) {
        console.error('AI form elements not found');
        showToast('Error: AI form not properly loaded. Please refresh the page.', 'error');
        return;
    }
    
    const question = questionInput.value.trim();
    const imageInput = document.getElementById('aiImageInput');
    const hasImage = imageInput && imageInput.files && imageInput.files.length > 0;
    
    if (!question && !hasImage) {
        showToast('Please enter a message or attach an image', 'error');
        return;
    }
    
    if (!currentUser) {
        console.error('No current user found');
        showToast('Error: Not logged in. Please log in again.', 'error');
        return;
    }
    
    // Read image as data URL if present (before we push to history so we can store it)
    let imageDataUrl = null;
    if (hasImage) {
        try {
            imageDataUrl = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = () => reject(new Error('Failed to read image'));
                reader.readAsDataURL(imageInput.files[0]);
            });
        } catch (e) {
            showToast('Could not read image. Try another file.', 'error');
            return;
        }
    }
    
    const questionText = question || (hasImage ? 'What do you see in this image?' : '');
    console.log('Getting AI advice for question:', questionText, 'User:', currentUser.username, 'Has image:', !!imageDataUrl);
    
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.textContent = 'Getting advice...';
    
    // Add user message to conversation history (with optional image)
    const userMsg = { role: 'user', content: questionText };
    if (imageDataUrl) userMsg.image = imageDataUrl;
    aiConversationHistory.push(userMsg);
    
    // Update display to show conversation (without loading indicator yet)
    updateConversationDisplay();
    
    // Show loading indicator AFTER updating display
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.id = 'ai-loading-indicator';
    loadingDiv.style.display = 'flex';
    loadingDiv.style.alignItems = 'center';
    loadingDiv.style.gap = '10px';
    loadingDiv.style.marginTop = '12px';
    loadingDiv.innerHTML = '<div class="spinner"></div> Thinking...';
    
    // Find the conversation container and add loading indicator
    const conversationContainer = responseDiv.querySelector('.conversation-container');
    if (conversationContainer) {
        conversationContainer.appendChild(loadingDiv);
    } else {
        responseDiv.appendChild(loadingDiv);
    }
    
    responseDiv.scrollTop = responseDiv.scrollHeight;
    
    try {
        // Get user preferences and notes for context (only on first message)
        let prefs = { likes: '', dislikes: '' };
        let notes = [];
        
        let medicalInfo = {};
        if (aiConversationHistory.length === 1) {
            // Load preferences, doctor notes, and doctor-recorded medical info for AI context
            try {
                const notesPromise = currentUser.patient_id
                    ? apiService.getDoctorNotesByPatientId(currentUser.patient_id)
                    : apiService.getDoctorNotes(currentUser.username);
                const medicalPromise = currentUser.patient_id
                    ? apiService.getMedicalInfoByPatientId(currentUser.patient_id)
                    : apiService.getMedicalInfo(currentUser.username);
                [prefs, notes, medicalInfo] = await Promise.all([
                    apiService.getLikesDislikes(currentUser.username),
                    notesPromise,
                    medicalPromise
                ]);
                if (!Array.isArray(notes)) notes = [];
                if (!medicalInfo || typeof medicalInfo !== 'object') medicalInfo = {};
            } catch (prefError) {
                console.warn('Could not load preferences/notes/medical for AI context:', prefError);
                prefs = { likes: '', dislikes: '' };
                notes = [];
                medicalInfo = {};
            }
        }
        
        // Get AI response with conversation history
        console.log('Calling AI API with:', {
            question,
            userName: currentUser.name,
            likes: prefs.likes || '',
            dislikes: prefs.dislikes || '',
            notesCount: notes.length,
            hasMedicalInfo: !!medicalInfo && Object.keys(medicalInfo).length > 0,
            conversationHistoryLength: aiConversationHistory.length - 1
        });
        
        // Build conversation_history for API (include image for user messages that have it)
        const historyForApi = aiConversationHistory.slice(0, -1).map(msg => {
            const out = { role: msg.role, content: msg.content || '' };
            if (msg.role === 'user' && msg.image) out.image = msg.image;
            return out;
        });

        const aiResponse = await apiService.getAIAdvice(
            questionText,
            currentUser.name,
            prefs.likes || '',
            prefs.dislikes || '',
            notes || [],
            historyForApi,
            medicalInfo,
            imageDataUrl
        );
        
        console.log('AI API response:', aiResponse);
        
        // Extract response text
        let responseText;
        if (typeof aiResponse === 'string') {
            responseText = aiResponse;
        } else if (aiResponse && aiResponse.response) {
            responseText = aiResponse.response;
        } else if (aiResponse) {
            responseText = JSON.stringify(aiResponse);
        } else {
            throw new Error('Empty response from AI service');
        }
        
        if (!responseText || responseText.trim() === '') {
            throw new Error('AI returned an empty response');
        }
        
        // Remove loading indicator
        const loadingIndicator = document.getElementById('ai-loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
        
        // Add AI response to conversation history
        aiConversationHistory.push({ role: 'assistant', content: responseText });
        
        // Update display
        updateConversationDisplay();
        responseDiv.scrollTop = responseDiv.scrollHeight;
        
        // Clear input and image
        document.getElementById('aiQuestion').value = '';
        const clearImgInput = document.getElementById('aiImageInput');
        if (clearImgInput) clearImgInput.value = '';
        const clearImgName = document.getElementById('aiImageName');
        if (clearImgName) clearImgName.textContent = '';
        const clearImgRemove = document.getElementById('aiImageRemoveBtn');
        if (clearImgRemove) clearImgRemove.style.display = 'none';
        
    } catch (error) {
        console.error('AI error:', error);
        
        // Try to remove loading indicator if it exists
        const loadingIndicator = document.getElementById('ai-loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
        
        const errorMsg = error.message || 'Could not get AI response. Please check your OpenAI API key configuration.';
        
        // Remove the user message from history if there was an error
        if (aiConversationHistory.length > 0 && aiConversationHistory[aiConversationHistory.length - 1].role === 'user') {
            aiConversationHistory.pop();
        }
        
        updateConversationDisplay();
        
        // Add error message to display
        const errorDiv = document.createElement('div');
        errorDiv.className = 'ai-message ai-error';
        errorDiv.innerHTML = `Error: ${escapeHtml(errorMsg)}`;
        responseDiv.appendChild(errorDiv);
        responseDiv.scrollTop = responseDiv.scrollHeight;
        
        showToast('Error getting AI advice', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Send';
    }
};

// Also make it available as a regular function for backwards compatibility
const getAIAdvice = window.getAIAdvice;

// Update conversation display
function updateConversationDisplay() {
    const responseDiv = document.getElementById('aiResponse');
    
    if (!responseDiv) {
        console.error('aiResponse element not found');
        return;
    }
    
    if (aiConversationHistory.length === 0) {
        responseDiv.innerHTML = '<p class="ai-placeholder">AI response will appear here...</p>';
        return;
    }
    
    // Check if loading indicator exists and preserve it
    const loadingIndicator = document.getElementById('ai-loading-indicator');
    const loadingHtml = loadingIndicator ? loadingIndicator.outerHTML : '';
    
    let html = '<div class="conversation-container">';
    
    aiConversationHistory.forEach((msg, index) => {
        if (msg.role === 'user') {
            const imgHtml = msg.image && String(msg.image).startsWith('data:image') ? `<div style="margin-top: 8px;"><img src="${String(msg.image).replace(/"/g, '&quot;')}" alt="Attached" style="max-width: 100%; max-height: 200px; border-radius: 8px; border: 1px solid #eee;"></div>` : '';
            html += `
                <div class="ai-message ai-user-message">
                    <strong>You:</strong> ${escapeHtml(msg.content || '').replace(/\n/g, '<br>')}
                    ${imgHtml}
                </div>
            `;
        } else if (msg.role === 'assistant') {
            html += `
                <div class="ai-message ai-assistant-message">
                    <strong>AI:</strong> ${formatAssistantMessageHtml(msg.content)}
                </div>
            `;
        }
    });
    
    // Add loading indicator back if it existed
    if (loadingHtml) {
        html += loadingHtml;
    }
    
    html += '</div>';
    responseDiv.innerHTML = html;
}

// Clear conversation (optional - can add a button for this)
function clearConversation() {
    aiConversationHistory = [];
    updateConversationDisplay();
    document.getElementById('aiQuestion').value = '';
    const imgInput = document.getElementById('aiImageInput');
    if (imgInput) imgInput.value = '';
    const imgName = document.getElementById('aiImageName');
    if (imgName) imgName.textContent = '';
    const imgRemove = document.getElementById('aiImageRemoveBtn');
    if (imgRemove) imgRemove.style.display = 'none';
}

// ——— Doctor: BMI & BMR Calculator (Mifflin-St Jeor) ———
function parseWeightToKg(weightStr) {
    if (!weightStr || typeof weightStr !== 'string') return null;
    const s = weightStr.trim().toLowerCase();
    const num = parseFloat(s.replace(/[^0-9.]/g, ''));
    if (isNaN(num)) return null;
    if (s.includes('kg')) return num;
    if (s.includes('lb') || s.includes('lbs')) return num * 0.45359237;
    return num * 0.45359237; // default assume lbs
}

function heightToM(feet, inches) {
    const f = parseFloat(feet);
    const i = parseFloat(inches) || 0;
    if (isNaN(f) && isNaN(i)) return null;
    const totalInches = (isNaN(f) ? 0 : f * 12) + (isNaN(i) ? 0 : i);
    return totalInches <= 0 ? null : totalInches * 0.0254;
}

function heightToCm(feet, inches) {
    const m = heightToM(feet, inches);
    return m == null ? null : m * 100;
}

function bmiCategory(bmi) {
    if (bmi == null || isNaN(bmi)) return '';
    if (bmi < 18.5) return 'Underweight';
    if (bmi < 25) return 'Normal';
    if (bmi < 30) return 'Overweight';
    return 'Obese';
}

function bmrMifflinStJeor(weightKg, heightCm, ageYears, sex) {
    if (weightKg == null || heightCm == null || ageYears == null) return null;
    const age = parseInt(ageYears, 10);
    if (isNaN(age)) return null;
    const w = parseFloat(weightKg);
    const h = parseFloat(heightCm);
    if (isNaN(w) || isNaN(h) || w <= 0 || h <= 0) return null;
    const base = (10 * w) + (6.25 * h) - (5 * age);
    const sexLower = (sex || '').toLowerCase();
    if (sexLower === 'male') return Math.round(base + 5);
    if (sexLower === 'female') return Math.round(base - 161);
    return Math.round(base); // other: use average
}

function updateDoctorBMICalculator() {
    const resultEl = document.getElementById('doctorBMIResult');
    if (!resultEl) return;
    const feetEl = document.getElementById('doctorPatientHeightFeet');
    const inchesEl = document.getElementById('doctorPatientHeightInches');
    const weightEl = document.getElementById('doctorPatientWeight');
    const ageEl = document.getElementById('doctorPatientAge');
    const sexEl = document.getElementById('doctorPatientSex');
    const feet = feetEl && feetEl.value.trim() !== '' ? parseFloat(feetEl.value) : null;
    const inches = inchesEl && inchesEl.value.trim() !== '' ? parseFloat(inchesEl.value) : null;
    const weightKg = weightEl ? parseWeightToKg(weightEl.value) : null;
    const heightM = heightToM(feet, inches);
    const heightCm = heightToCm(feet, inches);
    const age = ageEl && ageEl.value.trim() !== '' ? parseInt(ageEl.value, 10) : null;
    const sex = sexEl ? sexEl.value : '';

    if ((weightKg == null || heightM == null || heightM <= 0) && !weightEl?.value.trim() && !feet && inches == null) {
        resultEl.innerHTML = '<span style="color: var(--text-light);">Enter height (ft/in) and weight above, then click Calculate.</span>';
        return;
    }

    let html = '';
    if (weightKg != null && heightM != null && heightM > 0) {
        const bmi = weightKg / (heightM * heightM);
        const category = bmiCategory(bmi);
        html += `<p><strong>BMI:</strong> ${bmi.toFixed(1)} <span style="color: var(--text-light);">(${category})</span></p>`;
    } else {
        html += '<p><strong>BMI:</strong> <span style="color: var(--text-light);">Enter height and weight.</span></p>';
    }

    if (weightKg != null && heightCm != null && age != null && !isNaN(age)) {
        const bmr = bmrMifflinStJeor(weightKg, heightCm, age, sex);
        if (bmr != null) {
            html += `<p><strong>BMR (Mifflin-St Jeor):</strong> ${bmr} kcal/day</p>`;
            html += '<p style="font-size: 0.85rem; color: var(--text-light); margin-top: 8px;">Uses age, sex, height (cm), and weight (kg).</p>';
        } else {
            html += '<p><strong>BMR:</strong> <span style="color: var(--text-light);">Enter age, sex, height, and weight.</span></p>';
        }
    } else {
        html += '<p><strong>BMR (Mifflin-St Jeor):</strong> <span style="color: var(--text-light);">Enter age, sex, height, and weight.</span></p>';
    }
    resultEl.innerHTML = html;
}

// ——— Doctor: Personalized Nutrition Plan ———
function renderNutritionPlanFormatted(plan) {
    if (!plan || typeof plan !== 'object') return '';
    const arr = (v) => (Array.isArray(v) ? v : [v].filter(Boolean));
    const str = (v) => (v != null && v !== '' ? String(v) : '—');
    const list = (items) => arr(items).map(i => `<li>${escapeHtml(str(i))}</li>`).join('');
    const meal = (day, mealName) => str(plan[`day${day}_${mealName}`]);
    const html = `
<div class="np-title">Your Personalized Nutrition Plan</div>

<div class="np-section">
  <div class="np-section-header np-section-orange">Calorie Estimate</div>
  <table>
    <tr><td>Maintenance Calories</td><td>${escapeHtml(str(plan.maintenance_calories))} per day</td></tr>
    <tr><td>Weight Loss Calories (One pound/week)</td><td>${escapeHtml(str(plan.weight_loss_calories))} per day</td></tr>
  </table>
</div>

<div class="np-section">
  <div class="np-section-header np-section-green">Macro Distribution</div>
  <p>Carbs: ${escapeHtml(str(plan.carbs_g))} g/day &nbsp;&nbsp; Protein: ${escapeHtml(str(plan.protein_g))} g/day &nbsp;&nbsp; Fats: ${escapeHtml(str(plan.fats_g))} g/day</p>
</div>

<div class="np-section">
  <div class="np-section-header np-section-blue">General Food Recommendations</div>
  <div class="np-two-col">
    <div><div class="np-subhead">Foods to Include:</div><ul class="np-list">${list(plan.foods_include)}</ul></div>
    <div><div class="np-subhead">Foods to Avoid:</div><ul class="np-list">${list(plan.foods_avoid)}</ul></div>
  </div>
</div>

<div class="np-section">
  <div class="np-section-header np-section-green">3-Day Meal Plan</div>
  <table>
    <tr><th></th><th>Day 1</th><th>Day 2</th><th>Day 3</th></tr>
    <tr><td><strong>Breakfast:</strong></td><td>${escapeHtml(meal(1, 'breakfast'))}</td><td>${escapeHtml(meal(2, 'breakfast'))}</td><td>${escapeHtml(meal(3, 'breakfast'))}</td></tr>
    <tr><td><strong>Lunch:</strong></td><td>${escapeHtml(meal(1, 'lunch'))}</td><td>${escapeHtml(meal(2, 'lunch'))}</td><td>${escapeHtml(meal(3, 'lunch'))}</td></tr>
    <tr><td><strong>Dinner:</strong></td><td>${escapeHtml(meal(1, 'dinner'))}</td><td>${escapeHtml(meal(2, 'dinner'))}</td><td>${escapeHtml(meal(3, 'dinner'))}</td></tr>
  </table>
</div>

<div class="np-section">
  <div class="np-section-header np-section-blue">Sample Grocery List</div>
  <div class="np-two-col">
    <div>
      <div class="np-subhead">Produce:</div><ul class="np-list">${list(plan.grocery_produce)}</ul>
      <div class="np-subhead">Grains:</div><ul class="np-list">${list(plan.grocery_grains)}</ul>
    </div>
    <div>
      <div class="np-subhead">Proteins:</div><ul class="np-list">${list(plan.grocery_proteins)}</ul>
      <div class="np-subhead">Fats & Extras:</div><ul class="np-list">${list(plan.grocery_fats_extras)}</ul>
    </div>
  </div>
</div>

<div class="np-section">
  <div class="np-section-header np-section-orange">My SMART Goal</div>
  <div class="np-smart-line">${escapeHtml(str(plan.smart_goal))}</div>
</div>

<div class="np-section np-references">
  <div class="np-subhead">References:</div>
  <p class="np-references-body">${formatAssistantMessageHtml(str(plan.references))}</p>
</div>`;
    return html;
}

async function generateDoctorNutritionPlan() {
    const usernameInput = document.getElementById('doctorPatientUsername');
    const username = usernameInput ? usernameInput.value.trim() : '';
    const planFormatted = document.getElementById('doctorNutritionPlanFormatted');
    const planEl = document.getElementById('doctorNutritionPlan');
    const btn = document.getElementById('doctorGeneratePlanBtn');
    const printBtn = document.getElementById('doctorNutritionPlanPrintBtn');
    if (!username) {
        showToast('Load a patient first', 'error');
        return;
    }
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = 'Generating...';
    if (planFormatted) { planFormatted.innerHTML = '<p>Generating personalized nutrition plan...</p>'; planFormatted.style.display = 'block'; }
    if (planEl) { planEl.style.display = 'none'; planEl.value = ''; }
    if (printBtn) printBtn.style.display = 'none';
    try {
        const input = /^\d{6}$/.test(username) ? { patient_id: username } : { username };
        const res = await apiService.generateNutritionPlan(input);
        const plan = res && res.plan;
        if (plan && typeof plan === 'object' && !plan._raw) {
            const html = renderNutritionPlanFormatted(plan);
            if (planFormatted) { planFormatted.innerHTML = html; planFormatted.style.display = 'block'; }
            if (planEl) planEl.style.display = 'none';
            if (printBtn) printBtn.style.display = 'inline';
        } else {
            const raw = (plan && plan._raw) ? plan._raw : (typeof plan === 'string' ? plan : 'No plan generated.');
            if (planFormatted) { planFormatted.innerHTML = '<pre style="white-space: pre-wrap; margin:0;">' + escapeHtml(raw) + '</pre>'; planFormatted.style.display = 'block'; }
            if (printBtn) printBtn.style.display = 'inline';
        }
        showToast('Plan generated', 'success');
    } catch (e) {
        if (planFormatted) { planFormatted.innerHTML = ''; planFormatted.style.display = 'none'; }
        if (planEl) { planEl.value = ''; planEl.style.display = 'block'; }
        showToast(e.message || 'Failed to generate plan', 'error');
        console.error('Generate nutrition plan error:', e);
    }
    btn.disabled = false;
    btn.textContent = 'Generate with AI';
}

function printNutritionPlan() {
    const container = document.getElementById('doctorNutritionPlanFormatted');
    if (!container || !container.innerHTML.trim()) {
        showToast('Generate a plan first', 'error');
        return;
    }
    const win = window.open('', '_blank');
    if (!win) {
        showToast('Allow popups to print', 'error');
        return;
    }
    win.document.write(`
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Your Personalized Nutrition Plan</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; max-width: 800px; margin: 0 auto; font-size: 14px; line-height: 1.5; color: #1a1a1a; }
    .np-title { font-size: 1.5rem; font-weight: 700; color: #1e3a5f; margin-bottom: 20px; text-align: center; }
    .np-section { margin-bottom: 20px; }
    .np-section-header { font-weight: 700; padding: 8px 12px; margin: 0 0 10px 0; border-radius: 4px; font-size: 1rem; }
    .np-section-orange { background: #e8a64a; color: #1a1a1a; }
    .np-section-green { background: #7cb342; color: #1a1a1a; }
    .np-section-blue { background: #5c9ead; color: #fff; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
    th, td { border: 1px solid #ddd; padding: 10px 12px; text-align: left; }
    th { background: #f5f5f5; font-weight: 600; }
    .np-two-col { display: flex; gap: 24px; flex-wrap: wrap; }
    .np-two-col > div { flex: 1; min-width: 200px; }
    .np-list { list-style: none; padding: 0; margin: 0; }
    .np-list li { padding: 4px 0; padding-left: 16px; position: relative; }
    .np-list li::before { content: "•"; position: absolute; left: 0; font-weight: bold; }
    .np-subhead { font-weight: 600; margin: 10px 0 6px 0; color: #333; }
    .np-smart-line { border-bottom: 1px solid #333; min-height: 24px; padding: 4px 0; }
  </style>
</head>
<body>
  ${container.innerHTML}
</body>
</html>`);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); win.close(); }, 250);
}

// ——— Doctor: AI Assistant ———
function updateDoctorAIDisplay() {
    const el = document.getElementById('doctorAIResponse');
    if (!el) return;
    if (doctorAIConversationHistory.length === 0) {
        el.innerHTML = '';
        return;
    }
    const blocks = doctorAIConversationHistory.map(function (msg) {
        if (msg.role === 'user') {
            return '<div class="doctor-ai-line doctor-ai-user-line"><strong>You:</strong> ' + escapeHtml(msg.content || '').replace(/\n/g, '<br>') + '</div>';
        }
        return '<div class="doctor-ai-line doctor-ai-assistant-line"><strong>AI:</strong> ' + formatAssistantMessageHtml(msg.content || '') + '</div>';
    });
    el.innerHTML = blocks.join('');
}

async function sendDoctorAIMessage() {
    const questionEl = document.getElementById('doctorAIQuestion');
    const responseEl = document.getElementById('doctorAIResponse');
    const btn = document.getElementById('doctorAISendBtn');
    const question = questionEl ? questionEl.value.trim() : '';
    if (!question) {
        showToast('Enter a question', 'error');
        return;
    }
    if (!currentUser) return;
    doctorAIConversationHistory.push({ role: 'user', content: question });
    if (questionEl) questionEl.value = '';
    updateDoctorAIDisplay();
    if (btn) { btn.disabled = true; btn.textContent = 'Sending...'; }
    const patientContext = (typeof window.doctorCurrentPatientContext !== 'undefined') ? (window.doctorCurrentPatientContext || '') : '';
    const historyForApi = doctorAIConversationHistory.slice(0, -1).map(m => ({ role: m.role, content: m.content || '' }));
    try {
        const res = await apiService.getAIAdvice(
            question,
            currentUser.name,
            '', '', [],
            historyForApi,
            {},
            null,
            'doctor',
            patientContext
        );
        const text = (res && res.response) ? res.response : (typeof res === 'string' ? res : '');
        doctorAIConversationHistory.push({ role: 'assistant', content: text });
        updateDoctorAIDisplay();
        if (responseEl) responseEl.scrollTop = responseEl.scrollHeight;
    } catch (e) {
        doctorAIConversationHistory.pop();
        updateDoctorAIDisplay();
        showToast(e.message || 'AI request failed', 'error');
        console.error('Doctor AI error:', e);
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Send'; }
}

// Doctor Home
async function showDoctorHome() {
    showScreen('doctorHome');
    document.getElementById('doctorWelcome').textContent = `Doctor — ${currentUser.name}`;
    document.getElementById('doctorPatientInfo').style.display = 'none';
    document.getElementById('doctorPatientUsername').value = '';
    window.doctorCurrentPatientContext = '';
    // Set patient sign-up QR code to current site + #register (so scan opens registration)
    var registerUrl = window.location.origin + (window.location.pathname || '/') + '#register';
    if (!window.location.pathname || window.location.pathname === '/') registerUrl = window.location.origin + '/#register';
    var qrContainer = document.getElementById('doctorQRCodeContainer');
    var qrUrlEl = document.getElementById('doctorQRCodeUrl');
    if (qrUrlEl) qrUrlEl.textContent = registerUrl;
    if (qrContainer) {
        qrContainer.innerHTML = '';
        if (typeof QRCode !== 'undefined') {
            try {
                new QRCode(qrContainer, { text: registerUrl, width: 200, height: 200 });
            } catch (e) {
                var img = document.createElement('img');
                img.alt = 'Scan to create account';
                img.width = 200;
                img.height = 200;
                img.src = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + encodeURIComponent(registerUrl);
                qrContainer.appendChild(img);
            }
        } else {
            var img = document.createElement('img');
            img.alt = 'Scan to create account';
            img.width = 200;
            img.height = 200;
            img.src = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + encodeURIComponent(registerUrl);
            qrContainer.appendChild(img);
        }
    }
    await loadDoctorPatientList();
}

/** Populate the doctor's patient dropdown from the API. */
async function loadDoctorPatientList() {
    const select = document.getElementById('doctorPatientSelect');
    if (!select) return;
    const firstOption = select.options[0];
    select.innerHTML = '';
    if (firstOption) select.appendChild(firstOption);
    try {
        const patients = await apiService.getPatients();
        if (!Array.isArray(patients)) return;
        patients.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.username || '';
            const label = [p.name, p.username].filter(Boolean).join(' — ');
            opt.textContent = p.patient_id ? `${label} (ID: ${p.patient_id})` : label;
            select.appendChild(opt);
        });
    } catch (e) {
        console.warn('Could not load patient list for dropdown:', e);
    }
}

/** When doctor selects a patient from dropdown, set input and load. */
function onDoctorPatientSelectChange() {
    const select = document.getElementById('doctorPatientSelect');
    const input = document.getElementById('doctorPatientUsername');
    if (!select || !input) return;
    const value = select.value;
    if (!value) return;
    input.value = value;
    loadPatient(value);
}

async function loadPatient(usernameOverride = null) {
    // Use provided username or get from input field
    let searchInput = usernameOverride;
    if (!searchInput) {
        const usernameInput = document.getElementById('doctorPatientUsername');
        searchInput = usernameInput ? usernameInput.value.trim() : '';
    }
    
    if (!searchInput) {
        showToast('Please enter a patient username or Patient ID', 'error');
        return;
    }
    
    // Make sure the username is in the input field for display
    const usernameInput = document.getElementById('doctorPatientUsername');
    if (usernameInput && !usernameInput.value.trim()) {
        usernameInput.value = searchInput;
    }

    console.log('=== loadPatient function called ===');
    const patientInfoDiv = document.getElementById('doctorPatientInfo');
    console.log('patientInfoDiv found:', !!patientInfoDiv);
    
    if (!patientInfoDiv) {
        console.error('doctorPatientInfo element not found!');
        showToast('Error: Patient info container not found. Please refresh the page.', 'error');
        return;
    }
    
    console.log('Setting loading state...');
    patientInfoDiv.style.display = 'block';
    
    // Create or show loading overlay instead of replacing HTML
    let loadingOverlay = document.getElementById('patientLoadingOverlay');
    if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'patientLoadingOverlay';
        loadingOverlay.style.cssText = 'position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.9); display: flex; align-items: center; justify-content: center; z-index: 1000; border-radius: 8px;';
        loadingOverlay.innerHTML = '<div class="loading">Loading patient...</div>';
        patientInfoDiv.style.position = 'relative';
        patientInfoDiv.appendChild(loadingOverlay);
    } else {
        loadingOverlay.style.display = 'flex';
    }
    console.log('Loading overlay shown, making API call...');

    try {
        console.log('=== LOADING PATIENT ===');
        console.log('Input:', searchInput);
        console.log('API Base URL:', apiService.baseUrl);
        
        let user;
        let searchMethod = '';
        
        try {
            // Check if input is a 6-digit number (Patient ID)
            if (/^\d{6}$/.test(searchInput)) {
                searchMethod = 'Patient ID';
                console.log('Searching by Patient ID:', searchInput);
                console.log('Calling: getUserByPatientId');
                user = await apiService.getUserByPatientId(searchInput);
                console.log('getUserByPatientId returned:', user);
            } else {
                searchMethod = 'Username';
                console.log('Searching by username:', searchInput);
                console.log('Calling: getUserByUsername');
                user = await apiService.getUserByUsername(searchInput);
                console.log('getUserByUsername returned:', user);
            }
        } catch (apiError) {
            console.error('=== API CALL FAILED ===');
            console.error('Error type:', apiError.constructor.name);
            console.error('Error message:', apiError.message);
            console.error('Error stack:', apiError.stack);
            
            // Hide loading overlay
            const loadingOverlay = document.getElementById('patientLoadingOverlay');
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }
            
            showToast(`Error: ${apiError.message || 'Failed to load patient'}`, 'error');
            
            // Show error message without wiping out the form
            let errorDiv = document.getElementById('patientLoadError');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.id = 'patientLoadError';
                errorDiv.className = 'error-message';
                errorDiv.style.cssText = 'padding: 20px; background: #ffe0e0; border-radius: 8px; color: #d32f2f; margin-bottom: 20px;';
                patientInfoDiv.insertBefore(errorDiv, patientInfoDiv.firstChild);
            }
            errorDiv.innerHTML = `
                <strong>Error loading patient:</strong><br>
                ${escapeHtml(apiError.message || 'Unknown error')}<br><br>
                <small>Check browser console (F12) for more details.</small><br>
                <small>Make sure your server is running: python server.py</small>
            `;
            return;
        }
        
        console.log('User response:', user);
        
        // Hide loading overlay
        const loadingOverlay = document.getElementById('patientLoadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
        
        // Remove any previous error messages
        const errorDiv = document.getElementById('patientLoadError');
        if (errorDiv) {
            errorDiv.remove();
        }
        
        if (!user) {
            console.error('No user returned from API');
            showToast('Patient not found. Try username or 6-digit Patient ID', 'error');
            
            // Show error without wiping form
            let errorMsg = document.getElementById('patientLoadError');
            if (!errorMsg) {
                errorMsg = document.createElement('div');
                errorMsg.id = 'patientLoadError';
                errorMsg.className = 'error-message';
                errorMsg.style.cssText = 'padding: 20px; background: #ffe0e0; border-radius: 8px; color: #d32f2f; margin-bottom: 20px;';
                patientInfoDiv.insertBefore(errorMsg, patientInfoDiv.firstChild);
            }
            errorMsg.innerHTML = '<strong>Patient not found</strong><br>Try searching by username or 6-digit Patient ID (e.g., 123456)';
            return;
        }
        
        if (!user.username) {
            console.error('User object missing username:', user);
            showToast('Invalid patient data. Please try again.', 'error');
            
            let errorMsg = document.getElementById('patientLoadError');
            if (!errorMsg) {
                errorMsg = document.createElement('div');
                errorMsg.id = 'patientLoadError';
                errorMsg.className = 'error-message';
                errorMsg.style.cssText = 'padding: 20px; background: #ffe0e0; border-radius: 8px; color: #d32f2f; margin-bottom: 20px;';
                patientInfoDiv.insertBefore(errorMsg, patientInfoDiv.firstChild);
            }
            errorMsg.innerHTML = '<strong>Invalid patient data</strong><br>The server returned invalid data. Please try again.';
            return;
        }

        // Load patient data - fetch all data separately to ensure we get everything
        const username = user.username; // Get username from user object
        let notes = [];
        let prefs = { likes: '', dislikes: '' };
        let medicalInfo = {};
        
        try {
            [notes, prefs, medicalInfo] = await Promise.all([
                apiService.getDoctorNotes(username).catch(() => []),
                apiService.getLikesDislikes(username).catch(() => ({ likes: '', dislikes: '' })),
                apiService.getMedicalInfo(username).catch(() => ({}))
            ]);
            console.log('Loaded medical info:', medicalInfo);
        } catch (error) {
            console.error('Error loading patient data:', error);
            // Continue with empty data
        }

        // Update UI - Basic Info (with null checks). Use API username for notes/add-note so notes are stored under username, not patient_id.
        const doctorUsernameInput = document.getElementById('doctorPatientUsername');
        if (doctorUsernameInput && user.username) {
            doctorUsernameInput.value = user.username;
        }
        const patientInfoContent = document.getElementById('patientInfoContent');
        if (patientInfoContent) {
            patientInfoContent.innerHTML = `
                <p><strong>Username:</strong> ${escapeHtml(user.username)}</p>
                ${user.patient_id ? `<p><strong>Patient ID:</strong> ${escapeHtml(user.patient_id)}</p>` : ''}
            `;
        } else {
            console.error('patientInfoContent not found after restore!');
        }
        
        const nameEl = document.getElementById('doctorPatientName');
        const ageEl = document.getElementById('doctorPatientAge');
        const sexEl = document.getElementById('doctorPatientSex');
        
        if (nameEl) nameEl.value = user.name || '';
        if (ageEl) ageEl.value = user.age || '';
        if (sexEl) sexEl.value = user.sex || '';
        
        // Use the fetched medical info (not from user object)
        
        // Safely set all medical info fields
        const heightFeetEl = document.getElementById('doctorPatientHeightFeet');
        const heightInchesEl = document.getElementById('doctorPatientHeightInches');
        const weightEl = document.getElementById('doctorPatientWeight');
        const historyEl = document.getElementById('doctorPastMedicalHistory');
        const goalsEl = document.getElementById('doctorPatientGoals');
        const allergiesEl = document.getElementById('doctorFoodAllergies');
        const activityEl = document.getElementById('doctorPhysicalActivity');
        const medicationsEl = document.getElementById('doctorCurrentMedications');
        
        if (heightFeetEl) heightFeetEl.value = medicalInfo.height_feet != null && medicalInfo.height_feet !== '' ? String(medicalInfo.height_feet) : '';
        if (heightInchesEl) heightInchesEl.value = medicalInfo.height_inches != null && medicalInfo.height_inches !== '' ? String(medicalInfo.height_inches) : '';
        if (weightEl) weightEl.value = medicalInfo.weight || '';
        if (historyEl) historyEl.value = medicalInfo.past_medical_history || '';
        if (goalsEl) goalsEl.value = medicalInfo.patient_goals || '';
        if (allergiesEl) allergiesEl.value = medicalInfo.food_allergies || '';
        if (activityEl) activityEl.value = medicalInfo.physical_activity || '';
        if (medicationsEl) medicationsEl.value = medicalInfo.current_medications || '';

        // Update BMI & BMR calculator from loaded data
        updateDoctorBMICalculator();

        // Generate and display medical information summary
        const medicalSummary = generateMedicalSummary(user, medicalInfo, prefs);
        // Store plain-text patient context for doctor AI assistant
        window.doctorCurrentPatientContext = buildPatientContextText(user, medicalInfo, prefs, notes);
        
        // Display notes with medical summary (with null check)
        const notesList = document.getElementById('doctorNotesList');
        if (notesList) {
            let notesHTML = '';
            
            // Add medical summary at the top
            notesHTML += `
                <div class="medical-summary-card" style="background: #f8f9fa; border-left: 4px solid var(--primary-color); padding: 20px; margin-bottom: 20px; border-radius: 8px;">
                    <h4 style="margin: 0 0 15px 0; color: var(--primary-color);">Medical Information Summary</h4>
                    <div style="line-height: 1.8;">${medicalSummary}</div>
                </div>
            `;
            
            // Add individual notes
            if (notes.length === 0) {
                notesHTML += '<div class="empty-state">No additional notes yet.</div>';
            } else {
                notesHTML += notes.map(note => {
                    const date = new Date(note.created_at);
                    return `
                        <div class="note-item">
                            <div class="note-text">${escapeHtml(note.note)}</div>
                            <div class="note-date">${date.toLocaleString()}</div>
                        </div>
                    `;
                }).join('');
            }
            
            notesList.innerHTML = notesHTML;
        } else {
            console.warn('doctorNotesList element not found');
        }

        // Show the patient info div AFTER all elements are populated
        if (patientInfoDiv) {
            patientInfoDiv.style.display = 'block';
            console.log('Patient loaded successfully:', user.username);
            const patientSelect = document.getElementById('doctorPatientSelect');
            if (patientSelect) patientSelect.value = user.username || '';
        } else {
            console.error('doctorPatientInfo div not found!');
            showToast('Error: Patient info container not found', 'error');
        }
    } catch (error) {
        console.error('Error loading patient:', error);
        console.error('Error stack:', error.stack);
        const errorMsg = error.message || 'Error loading patient. Please check the console for details.';
        
        // Hide loading overlay
        const loadingOverlay = document.getElementById('patientLoadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
        
        // Show detailed error in console
        if (error.response) {
            console.error('API Error Response:', error.response);
        }
        
        showToast(`Error: ${errorMsg}`, 'error');
        
        // Show error without wiping out the form
        let errorDiv = document.getElementById('patientLoadError');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'patientLoadError';
            errorDiv.className = 'error-message';
            errorDiv.style.cssText = 'padding: 20px; background: #ffe0e0; border-radius: 8px; color: #d32f2f; margin-bottom: 20px;';
            patientInfoDiv.insertBefore(errorDiv, patientInfoDiv.firstChild);
        }
        errorDiv.innerHTML = `
            <strong>Error loading patient:</strong><br>
            ${escapeHtml(errorMsg)}<br><br>
            <small>Check browser console (F12) for more details.</small>
        `;
        patientInfoDiv.style.display = 'block';
    }
}

// Refresh the doctor's notes display with updated medical information
async function refreshDoctorNotesDisplay(username) {
    try {
        // Get updated data
        const [user, notes, prefs, medicalInfo] = await Promise.all([
            apiService.getUserByUsername(username).catch(() => apiService.getUserByPatientId(username)),
            apiService.getDoctorNotes(username).catch(() => []),
            apiService.getLikesDislikes(username).catch(() => ({ likes: '', dislikes: '' })),
            apiService.getMedicalInfo(username).catch(() => ({}))
        ]);
        
        if (!user) return;
        
        // Generate medical summary
        const medicalSummary = generateMedicalSummary(user, medicalInfo || {}, prefs || { likes: '', dislikes: '' });
        
        // Update notes display
        const notesList = document.getElementById('doctorNotesList');
        if (notesList) {
            let notesHTML = '';
            
            // Add medical summary at the top
            notesHTML += `
                <div class="medical-summary-card" style="background: #f8f9fa; border-left: 4px solid var(--primary-color); padding: 20px; margin-bottom: 20px; border-radius: 8px;">
                    <h4 style="margin: 0 0 15px 0; color: var(--primary-color);">Medical Information Summary</h4>
                    <div style="line-height: 1.8;">${medicalSummary}</div>
                </div>
            `;
            
            // Add individual notes
            if (notes.length === 0) {
                notesHTML += '<div class="empty-state">No additional notes yet.</div>';
            } else {
                notesHTML += notes.map(note => {
                    const date = new Date(note.created_at);
                    return `
                        <div class="note-item">
                            <div class="note-text">${escapeHtml(note.note)}</div>
                            <div class="note-date">${date.toLocaleString()}</div>
                        </div>
                    `;
                }).join('');
            }
            
            notesList.innerHTML = notesHTML;
        }
    } catch (error) {
        console.error('Error refreshing notes display:', error);
    }
}

async function updatePatientInfo() {
    const usernameInput = document.getElementById('doctorPatientUsername');
    const username = usernameInput ? usernameInput.value.trim() : '';
    const name = document.getElementById('doctorPatientName').value.trim();
    const age = document.getElementById('doctorPatientAge').value;
    const sex = document.getElementById('doctorPatientSex').value;

    if (!username) {
        showToast('Please load a patient first', 'error');
        return;
    }

    try {
        const ageValue = age ? parseInt(age) : null;
        await apiService.updateUser(username, name, ageValue, sex);
        showToast('Patient information updated', 'success');
        
        // Refresh the notes section to show updated medical summary
        await refreshDoctorNotesDisplay(username);
    } catch (error) {
        showToast('Error updating patient info', 'error');
        console.error('Error updating patient info:', error);
    }
}

async function saveDoctorMedicalInfo(section) {
    const username = document.getElementById('doctorPatientUsername').value.trim();
    
    if (!username) {
        showToast('Please load a patient first', 'error');
        return;
    }

    try {
        // Get current medical info
        let medicalInfo = await apiService.getMedicalInfo(username);
        
        // Update the specific section
        switch(section) {
            case 'biometric': {
                const feetEl = document.getElementById('doctorPatientHeightFeet');
                const inchesEl = document.getElementById('doctorPatientHeightInches');
                const feet = feetEl && feetEl.value.trim() !== '' ? parseInt(feetEl.value, 10) : null;
                const inches = inchesEl && inchesEl.value.trim() !== '' ? parseFloat(inchesEl.value) : null;
                medicalInfo.height_feet = (feet != null && !isNaN(feet)) ? feet : null;
                medicalInfo.height_inches = (inches != null && !isNaN(inches)) ? inches : null;
                medicalInfo.height = (feet != null || inches != null) ? [feet != null ? feet + ' ft' : '', inches != null ? inches + ' in' : ''].filter(Boolean).join(' ') : '';
                medicalInfo.weight = document.getElementById('doctorPatientWeight').value.trim();
                break;
            }
            case 'medical_history':
                medicalInfo.past_medical_history = document.getElementById('doctorPastMedicalHistory').value.trim();
                break;
            case 'goals':
                medicalInfo.patient_goals = document.getElementById('doctorPatientGoals').value.trim();
                break;
            case 'allergies':
                medicalInfo.food_allergies = document.getElementById('doctorFoodAllergies').value.trim();
                break;
            case 'activity':
                medicalInfo.physical_activity = document.getElementById('doctorPhysicalActivity').value.trim();
                break;
            case 'medications':
                medicalInfo.current_medications = document.getElementById('doctorCurrentMedications').value.trim();
                break;
        }
        
        await apiService.updateMedicalInfo(username, medicalInfo);
        showToast('Medical information saved', 'success');
        
        // Refresh the notes section to show updated medical summary
        await refreshDoctorNotesDisplay(username);
    } catch (error) {
        showToast('Error saving medical information', 'error');
        console.error('Error saving medical info:', error);
    }
}

async function addDoctorNote() {
    const username = document.getElementById('doctorPatientUsername').value.trim();
    const note = document.getElementById('doctorNoteText').value.trim();

    if (!username) {
        showToast('Please load a patient first', 'error');
        return;
    }

    if (!note) {
        showToast('Please enter a note', 'error');
        return;
    }

    try {
        await apiService.addDoctorNote(username, note);
        document.getElementById('doctorNoteText').value = '';
        showToast('Note added', 'success');
        
        // Refresh the notes section to show updated notes
        await refreshDoctorNotesDisplay(username);
    } catch (error) {
        showToast('Error adding note', 'error');
        console.error('Error adding note:', error);
    }
}

// Logout
function logout() {
    currentUser = null;
    doctorAIConversationHistory = [];
    aiConversationHistory = []; // Clear conversation on logout
    localStorage.removeItem('currentUser');
    showScreen('loginScreen');
    // Clear forms
    document.getElementById('loginForm').reset();
    document.getElementById('registerForm').reset();
    // Force-clear login fields so browser autofill doesn't leave previous account when switching Patient/Doctor
    var loginErr = document.getElementById('loginError');
    if (loginErr) loginErr.textContent = '';
    setTimeout(function () {
        var u = document.getElementById('loginUsername');
        var p = document.getElementById('loginPassword');
        if (u) u.value = '';
        if (p) p.value = '';
    }, 0);
}

// Toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Turn assistant text into safe HTML: escape first, then markdown links [label](url) -> <a>.
 * Only http/https URLs allowed. Then linkify bare https? URLs outside of <a> tags. Newlines -> <br>.
 */
function formatAssistantMessageHtml(text) {
    if (text == null || text === '') return '';
    let s = escapeHtml(String(text));
    s = s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, function (_m, label, url) {
        try {
            const u = new URL(url);
            if (u.protocol !== 'http:' && u.protocol !== 'https:') return _m;
            const href = u.href.replace(/"/g, '&quot;');
            return '<a href="' + href + '" target="_blank" rel="noopener noreferrer">' + label + '</a>';
        } catch (e) {
            return _m;
        }
    });
    const parts = s.split(/(<a\s[^>]*>[\s\S]*?<\/a>)/gi);
    s = parts.map(function (chunk) {
        if (/^<a\s/i.test(chunk)) return chunk;
        return chunk.replace(/(https?:\/\/[^\s<]+)/gi, function (raw) {
            try {
                const m = raw.match(/^(https?:\/\/[^\s<]+?)([),.;]+)$/i);
                let url = m ? m[1] : raw;
                const trailing = m ? m[2] : '';
                const u = new URL(url);
                if (u.protocol !== 'http:' && u.protocol !== 'https:') return raw;
                const href = u.href.replace(/"/g, '&quot;');
                return '<a href="' + href + '" target="_blank" rel="noopener noreferrer">' + url + '</a>' + trailing;
            } catch (e) {
                return raw;
            }
        });
    }).join('');
    return s.replace(/\n/g, '<br>');
}

