// Main Application Logic
window.WELLBEING_APP_JS_VERSION = '6.0';

var ONBOARDING_START_TOKEN = '__ONBOARDING_START__';
var userOnboardingActive = false;
var userOnboardingKickoffStarted = false;

// Current user state
let currentUser = null;

// AI Conversation history - stores conversation for current session
let aiConversationHistory = [];
/** Set by Chrome/Edge beforeinstallprompt; used by header Install button. */
let deferredPwaPrompt = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    console.log('Wellbeing app.js version:', window.WELLBEING_APP_JS_VERSION);
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

    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        deferredPwaPrompt = e;
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

    // User preferences form
    document.getElementById('userPrefsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveUserPreferences();
    });

    // User account form
    document.getElementById('userAccountForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveUserAccount();
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

    const userAiPrintBtn = document.getElementById('userAiPrintBtn');
    if (userAiPrintBtn) {
        userAiPrintBtn.addEventListener('click', () => printUserAiRecommendations());
    }
    const userOnboardingFinishBtn = document.getElementById('userOnboardingFinishBtn');
    if (userOnboardingFinishBtn) {
        userOnboardingFinishBtn.addEventListener('click', () => finishUserOnboarding());
    }
    document.addEventListener('click', function (e) {
        const rateBtn = e.target.closest('.ai-rate-btn');
        if (rateBtn) {
            e.preventDefault();
            handleAiRateClick(rateBtn);
        }
    });
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
            role: user.role || 'User',
            patient_id: user.patient_id || '',
            age: user.age || null,
            feedback_token: user.feedback_token || user.feedbackToken || '',
            onboarding_completed: user.onboarding_completed !== false && user.onboarding_completed !== 0
        };

        if (!userData.username) {
            errorDiv.textContent = 'Invalid response from server. Please check the console.';
            return;
        }

        // Map legacy Patient/Doctor roles to User (doctor portal removed)
        const r = (userData.role || '').toLowerCase();
        if (r === 'patient' || r === 'doctor') userData.role = 'User';
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
    const role = 'User';
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

        if (response.patient_id) {
            showToast(`Registration successful! Your User ID is: ${response.patient_id}. Please log in.`, 'success');
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

// Show user home
function showUserHome() {
    if (!currentUser) {
        showScreen('loginScreen');
        return;
    }
    showUserAppHome();
}

function isUserOnboardingPending() {
    return !!(currentUser
        && currentUser.role
        && ['user','patient'].includes(currentUser.role.toLowerCase())
        && (currentUser.onboarding_completed === false || currentUser.onboarding_completed === 0));
}

function updateUserOnboardingBanner() {
    const banner = document.getElementById('userOnboardingBanner');
    const subtitle = document.getElementById('userAiSubtitle');
    const show = userOnboardingActive && isUserOnboardingPending();
    if (banner) banner.style.display = show ? 'block' : 'none';
    if (subtitle) {
        subtitle.textContent = show
            ? 'Quick welcome chat — answer one question at a time so I can tailor your advice.'
            : 'Ask me anything about your wellbeing, recipes, or health questions!';
    }
}

async function initUserOnboardingUi() {
    if (!currentUser || !['user','patient'].includes(currentUser.role.toLowerCase())) {
        userOnboardingActive = false;
        updateUserOnboardingBanner();
        return;
    }
    if (currentUser.onboarding_completed === undefined) {
        try {
            const user = await apiService.getUserByUsername(currentUser.username);
            currentUser.onboarding_completed = user.onboarding_completed !== false;
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
        } catch (e) {
            console.warn('Could not load onboarding status:', e);
        }
    }
    userOnboardingActive = isUserOnboardingPending();
    updateUserOnboardingBanner();
    if (userOnboardingActive && aiConversationHistory.length === 0 && !userOnboardingKickoffStarted) {
        await startUserOnboardingInterview();
    }
}

async function startUserOnboardingInterview() {
    if (!currentUser || userOnboardingKickoffStarted || !userOnboardingActive) return;
    userOnboardingKickoffStarted = true;
    const responseDiv = document.getElementById('aiResponse');
    const submitBtn = document.getElementById('aiSubmitBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Starting...';
    }
    if (responseDiv) {
        responseDiv.innerHTML = '<div class="conversation-container"><div class="loading" style="display:flex;align-items:center;gap:10px;margin-top:12px;"><div class="spinner"></div> Starting your welcome chat...</div></div>';
    }
    try {
        const res = await apiService.getAIAdvice(
            ONBOARDING_START_TOKEN,
            currentUser.name,
            '', '', [], [],
            {},
            null,
            null,
            '',
            currentUser.username,
            currentUser.username,
            '', '',
            true
        );
        const text = (res && res.response) ? res.response : '';
        if (!text || !String(text).trim()) {
            throw new Error('Empty welcome message from AI');
        }
        aiConversationHistory.push({
            role: 'assistant',
            content: text,
            references: (res && Array.isArray(res.references)) ? res.references : [],
            log_id: (res && res.log_id) ? res.log_id : null,
            rating: null
        });
        updateConversationDisplay();
        if (responseDiv) responseDiv.scrollTop = responseDiv.scrollHeight;
    } catch (e) {
        userOnboardingKickoffStarted = false;
        if (responseDiv) {
            responseDiv.innerHTML = '<p class="ai-placeholder">Could not start welcome chat. Type a message below to begin.</p>';
        }
        console.error('Onboarding kickoff error:', e);
        showToast(e.message || 'Could not start welcome chat', 'error');
    }
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Send';
    }
}

async function finishUserOnboarding() {
    if (!currentUser || !userOnboardingActive) return;
    const btn = document.getElementById('userOnboardingFinishBtn');
    const historyForApi = aiConversationHistory.map(function (m) {
        return { role: m.role, content: m.content || '' };
    });
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving...';
    }
    try {
        await apiService.finishUserOnboarding(currentUser.username, historyForApi);
        currentUser.onboarding_completed = true;
        localStorage.setItem('currentUser', JSON.stringify(currentUser));
        userOnboardingActive = false;
        updateUserOnboardingBanner();
        showToast('Saved to your profile — thanks for sharing!', 'success');
    } catch (e) {
        showToast(e.message || 'Could not save intro', 'error');
    }
    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Save intro to my profile';
    }
}

// User Home
async function showUserAppHome() {
    console.log('Showing user home for:', currentUser);
    showScreen('userHome');
    
    const welcomeEl = document.getElementById('userWelcome');
    if (welcomeEl) {
        welcomeEl.textContent = `Welcome, ${currentUser.name}`;
    }

    // Display Patient ID under name
    await displayUserIdInHeader();

    // Verify tabs are present
    const tabsEl = document.querySelector('.user-nav-tabs');
    if (!tabsEl) {
        console.error('ERROR: User navigation tabs not found in HTML!');
        alert('ERROR: User tabs not found. Please refresh the page or check if index.html has been updated correctly.');
        return;
    }
    
    console.log('User tabs verified, showing main tab...');
    
    // Show main tab by default
    showUserTab('main');

    updatePwaInstallButtonVisibility();

    // Load account information
    await loadUserAccount();
    
    const aiResponseEl = document.getElementById('aiResponse');
    const aiQuestionEl = document.getElementById('aiQuestion');
    if (aiResponseEl) {
        if (aiConversationHistory.length > 0) {
            updateConversationDisplay();
        } else {
            aiResponseEl.innerHTML = '<p class="ai-placeholder">AI response will appear here...</p>';
        }
    }
    if (aiQuestionEl) {
        aiQuestionEl.value = '';
    }

    await initUserOnboardingUi();
}

// User Tab Navigation - Make it globally accessible
window.showUserTab = function showUserTab(tabName) {
    console.log('Switching to tab:', tabName);
    
    // Hide all tab contents
    document.querySelectorAll('.user-tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab content
    const selectedTab = document.getElementById(`userTab-${tabName}`);
    if (selectedTab) {
        selectedTab.classList.add('active');
        console.log('Tab content shown:', selectedTab.id);
    } else {
        console.error('Tab content not found:', `userTab-${tabName}`);
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
        loadUserAccount();
    }
}

async function displayUserIdInHeader() {
    // Load patient ID and display in header
    console.log('displayUserIdInHeader called, currentUser:', currentUser);
    
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
        
        const patientIdHeader = document.getElementById('userIdHeader');
        const patientIdHeaderValue = document.getElementById('userIdHeaderValue');
        
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

async function loadUserAccount() {
    // Load user info
    try {
        const user = await apiService.getUserByUsername(currentUser.username);
        if (user) {
            currentUser.name = user.name || currentUser.name;
            currentUser.age = user.age || null;
            currentUser.patient_id = user.patient_id || currentUser.patient_id;
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            
            // Update patient ID display immediately if we have it
            const patientIdValue = document.getElementById('userIdValueAccount');
            if (patientIdValue && currentUser.patient_id) {
                patientIdValue.textContent = currentUser.patient_id;
            }
            
            // Update header display
            await displayUserIdInHeader();
        }
    } catch (error) {
        console.error('Error loading user info:', error);
    }
    
    // Display patient ID (will fetch if not already loaded)
    displayUserIdAccount();
    
    // Load name and age
    const nameEl = document.getElementById('userName');
    const ageEl = document.getElementById('userAge');
    if (nameEl) nameEl.value = currentUser.name || '';
    if (ageEl) ageEl.value = currentUser.age || '';
    
    // Load preferences
    try {
        const prefs = await apiService.getLikesDislikes(currentUser.username);
        const likesEl = document.getElementById('userLikes');
        const dislikesEl = document.getElementById('userDislikes');
        const religionEl = document.getElementById('userReligion');
        const cultureEl = document.getElementById('userCulture');
        if (likesEl) likesEl.value = prefs.likes || '';
        if (dislikesEl) dislikesEl.value = prefs.dislikes || '';
        if (religionEl) religionEl.value = prefs.religion || '';
        if (cultureEl) cultureEl.value = prefs.culture || '';
    } catch (error) {
        console.error('Error loading preferences:', error);
    }

    // Load notes summary
    
}

async function saveUserAccount() {
    const name = document.getElementById('userName').value.trim();
    const age = document.getElementById('userAge').value;
    
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

function displayUserIdAccount() {
    const patientIdValue = document.getElementById('userIdValueAccount');
    
    if (patientIdValue) {
        if (currentUser && currentUser.patient_id) {
            patientIdValue.textContent = currentUser.patient_id;
            console.log('Patient ID displayed:', currentUser.patient_id);
        } else {
            // Show loading state
            patientIdValue.textContent = 'Loading...';
            // Try to fetch patient_id if not in currentUser
            fetchUserIdAccount();
        }
    } else {
        console.error('Patient ID value element not found');
    }
}

async function fetchUserIdAccount() {
    try {
        const user = await apiService.getUserByUsername(currentUser.username);
        if (user && user.patient_id) {
            currentUser.patient_id = user.patient_id;
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            const patientIdValue = document.getElementById('userIdValueAccount');
            if (patientIdValue) {
                patientIdValue.textContent = user.patient_id;
            }
        } else {
            const patientIdValue = document.getElementById('userIdValueAccount');
            if (patientIdValue) {
                patientIdValue.textContent = 'Not available';
            }
        }
    } catch (error) {
        console.error('Error fetching patient ID:', error);
        const patientIdValue = document.getElementById('userIdValueAccount');
        if (patientIdValue) {
            patientIdValue.textContent = 'Error loading';
        }
    }
}

function copyUserIdAccount() {
    const patientIdValue = document.getElementById('userIdValueAccount');
    if (patientIdValue) {
        const text = patientIdValue.textContent;
        if (text && text !== 'Loading...' && text !== 'Not available' && text !== 'Error loading') {
            navigator.clipboard.writeText(text).then(() => {
                showToast('User ID copied to clipboard!', 'success');
            }).catch(err => {
                console.error('Failed to copy:', err);
                showToast('Failed to copy. Please select and copy manually.', 'error');
            });
        }
    }
}

function copyUserIdFromHeader() {
    if (currentUser && currentUser.patient_id) {
        navigator.clipboard.writeText(currentUser.patient_id).then(() => {
            showToast('User ID copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            showToast('Failed to copy. Please select and copy manually.', 'error');
        });
    }
}

// Removed - patient ID is now displayed in Account tab

async function saveUserPreferences() {
    const likes = document.getElementById('userLikes').value;
    const dislikes = document.getElementById('userDislikes').value;
    const religion = document.getElementById('userReligion').value;
    const culture = document.getElementById('userCulture').value;

    try {
        await apiService.upsertLikesDislikes(currentUser.username, likes, dislikes, religion, culture);
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
        // Get user preferences and profile medical info for context (only on first message)
        let prefs = { likes: '', dislikes: '', religion: '', culture: '' };
        let notes = [];
        
        let medicalInfo = {};
        if (aiConversationHistory.length === 1) {
            try {
                const medicalPromise = currentUser.patient_id
                    ? apiService.getMedicalInfoByPatientId(currentUser.patient_id)
                    : apiService.getMedicalInfo(currentUser.username);
                [prefs, medicalInfo] = await Promise.all([
                    apiService.getLikesDislikes(currentUser.username),
                    medicalPromise
                ]);
                if (!medicalInfo || typeof medicalInfo !== 'object') medicalInfo = {};
            } catch (prefError) {
                console.warn('Could not load preferences/medical for AI context:', prefError);
                prefs = { likes: '', dislikes: '', religion: '', culture: '' };
                medicalInfo = {};
            }
        }
        
        // Get AI response with conversation history
        console.log('Calling AI API with:', {
            question,
            userName: currentUser.name,
            likes: prefs.likes || '',
            dislikes: prefs.dislikes || '',
            religion: prefs.religion || '',
            culture: prefs.culture || '',
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
            imageDataUrl,
            null,
            '',
            currentUser.username,
            currentUser.username,
            prefs.religion || '',
            prefs.culture || '',
            userOnboardingActive
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
        
        // Add AI response to conversation history (structured PubMed refs from server)
        aiConversationHistory.push({
            role: 'assistant',
            content: responseText,
            references: (aiResponse && Array.isArray(aiResponse.references)) ? aiResponse.references : [],
            log_id: (aiResponse && aiResponse.log_id) ? aiResponse.log_id : null,
            rating: null
        });
        
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
                    <strong>AI:</strong> ${formatAssistantReplyHtml(msg.content, msg.references)}
                    ${formatAiRatingButtonsHtml(msg.log_id, msg.rating, index, 'user')}
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
    finalizeAiReferenceBlocks(responseDiv);
    updateUserAiPrintButtonVisibility();
}

function hasAiPrintableContent(history) {
    return Array.isArray(history) && history.some(function (m) {
        return m.role === 'assistant' && String(m.content || '').trim();
    });
}

function formatAiRatingButtonsHtml(logId, currentRating, msgIndex, historyKind) {
    if (!logId) return '';
    const upActive = currentRating === 1 ? ' is-active' : '';
    const downActive = currentRating === -1 ? ' is-active' : '';
    return (
        '<div class="ai-rating-row">' +
        '<span class="ai-rating-label">Was this helpful?</span>' +
        '<button type="button" class="ai-rate-btn ai-rate-up' + upActive + '" data-log-id="' + escapeHtml(String(logId)) + '" data-rating="1" data-msg-index="' + msgIndex + '" data-history="' + escapeHtml(historyKind) + '" aria-label="Thumbs up" title="Good response">👍</button>' +
        '<button type="button" class="ai-rate-btn ai-rate-down' + downActive + '" data-log-id="' + escapeHtml(String(logId)) + '" data-rating="-1" data-msg-index="' + msgIndex + '" data-history="' + escapeHtml(historyKind) + '" aria-label="Thumbs down" title="Poor response">👎</button>' +
        '</div>'
    );
}

async function handleAiRateClick(btn) {
    if (!btn || !currentUser) return;
    const logId = parseInt(btn.getAttribute('data-log-id'), 10);
    const rating = parseInt(btn.getAttribute('data-rating'), 10);
    const msgIndex = parseInt(btn.getAttribute('data-msg-index'), 10);
    const historyKind = btn.getAttribute('data-history');
    const hist = aiConversationHistory;
    const msg = hist[msgIndex];
    if (!msg || !logId) return;
    const newRating = (msg.rating === rating) ? 0 : rating;
    btn.disabled = true;
    try {
        await apiService.rateAiResponse({
            log_id: logId,
            rating: newRating,
            username: currentUser.username,
        });
        msg.rating = newRating || null;
        updateConversationDisplay();
        if (newRating === 1) showToast('Thanks — glad that helped', 'success');
        else if (newRating === -1) showToast('Thanks — we\'ll use this to improve future answers', 'success');
        else showToast('Rating cleared', 'success');
    } catch (e) {
        showToast(e.message || 'Could not save rating', 'error');
    } finally {
        btn.disabled = false;
    }
}

function updateUserAiPrintButtonVisibility() {
    const btn = document.getElementById('userAiPrintBtn');
    if (!btn) return;
    btn.style.display = hasAiPrintableContent(aiConversationHistory) ? 'inline-block' : 'none';
}

function buildAiPrintBodyHtml(messages) {
    if (!messages || !messages.length) return '';
    return messages.map(function (msg) {
        if (msg.role === 'user') {
            const imgNote = msg.image ? '<p class="ai-print-meta">[Image attached to this question]</p>' : '';
            return (
                '<section class="ai-print-exchange">' +
                '<div class="ai-print-label">Your question</div>' +
                '<div class="ai-print-user">' + escapeHtml(msg.content || '').replace(/\n/g, '<br>') + imgNote + '</div>' +
                '</section>'
            );
        }
        if (msg.role === 'assistant') {
            return (
                '<section class="ai-print-exchange">' +
                '<div class="ai-print-label">AI recommendation</div>' +
                '<div class="ai-print-assistant">' + formatAssistantReplyHtml(msg.content || '', msg.references) + '</div>' +
                '</section>'
            );
        }
        return '';
    }).join('');
}

function printAiRecommendations(messages, options) {
    options = options || {};
    if (!hasAiPrintableContent(messages)) {
        showToast('Nothing to print yet — ask the AI a question first', 'error');
        return;
    }
    const title = options.title || 'AI Recommendations';
    const subtitle = options.subtitle || 'Wellbeing Companion';
    const metaLines = (options.metaLines || []).filter(Boolean);
    const printedAt = new Date().toLocaleString();
    const bodyHtml = buildAiPrintBodyHtml(messages);

    const win = window.open('', '_blank');
    if (!win) {
        showToast('Allow popups to print', 'error');
        return;
    }
    const metaHtml = metaLines.map(function (line) {
        return '<p class="ai-print-meta-line">' + escapeHtml(line) + '</p>';
    }).join('');

    win.document.write(
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>' + escapeHtml(title) + '</title>' +
        '<style>' +
        'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 24px; max-width: 800px; margin: 0 auto; font-size: 14px; line-height: 1.55; color: #1a1a1a; }' +
        'h1 { font-size: 1.35rem; color: #1e3a5f; margin: 0 0 6px 0; text-align: center; }' +
        '.ai-print-subtitle { text-align: center; color: #555; margin: 0 0 8px 0; font-size: 0.95rem; }' +
        '.ai-print-meta-line { text-align: center; color: #666; margin: 2px 0; font-size: 0.85rem; }' +
        '.ai-print-exchange { margin-bottom: 22px; page-break-inside: avoid; }' +
        '.ai-print-label { font-weight: 700; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; color: #1e3a5f; margin-bottom: 8px; }' +
        '.ai-print-user { padding: 12px 14px; background: #f0f4ff; border-radius: 8px; border: 1px solid #d8dff7; }' +
        '.ai-print-assistant { padding: 12px 14px; background: #fff; border-radius: 8px; border: 1px solid #ddd; }' +
        '.ai-print-meta { font-size: 0.85rem; color: #666; margin: 8px 0 0 0; font-style: italic; }' +
        '.ai-references-block { margin-top: 12px; padding: 10px 12px; font-size: 0.85rem; background: #f8f9fc; border: 1px solid #ddd; border-radius: 6px; }' +
        '.ai-references-block ul { margin: 6px 0 0 1.1rem; padding: 0; }' +
        '.ai-references-block li { margin-bottom: 4px; }' +
        '.ai-sources-details > summary { display: none !important; }' +
        '.ai-sources-details > ul { display: block !important; }' +
        '.ai-references-block > ul:first-of-type > li { display: list-item !important; }' +
        'a { color: #1e3a5f; }' +
        '.ai-print-footer { margin-top: 28px; padding-top: 12px; border-top: 1px solid #ccc; font-size: 0.75rem; color: #666; }' +
        '@media print { body { padding: 12px; } }' +
        '</style></head><body>' +
        '<h1>' + escapeHtml(title) + '</h1>' +
        '<p class="ai-print-subtitle">' + escapeHtml(subtitle) + '</p>' +
        metaHtml +
        '<p class="ai-print-meta-line">Printed ' + escapeHtml(printedAt) + '</p>' +
        '<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">' +
        bodyHtml +
        '<div class="ai-print-footer">For educational purposes only. AI suggestions are not a substitute for professional medical advice. Discuss any changes with your care team.</div>' +
        '</body></html>'
    );
    win.document.close();
    win.focus();
    setTimeout(function () { win.print(); win.close(); }, 250);
}

function printUserAiRecommendations() {
    const name = (currentUser && currentUser.name) ? currentUser.name : 'User';
    printAiRecommendations(aiConversationHistory, {
        title: 'AI Wellbeing Recommendations',
        subtitle: 'Wellbeing Companion',
        metaLines: ['Prepared for: ' + name],
    });
}

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
    updateUserAiPrintButtonVisibility();
}

var AI_SOURCES_VISIBLE_COUNT = 2;

function formatPubMedReferenceLi(r, includeApa) {
    const line = escapeHtml(r.citation_short || r.title || ('PMID ' + r.pmid));
    const apa = (includeApa && r.citation_apa)
        ? '<div style="font-size:0.8rem;color:var(--text-light);margin-top:4px;">' + escapeHtml(r.citation_apa) + '</div>'
        : '';
    let url = (r.url || '').trim();
    try {
        url = new URL(url).href.replace(/"/g, '&quot;');
    } catch (e) {
        url = '';
    }
    const link = url ? ' <a href="' + url + '" target="_blank" rel="noopener noreferrer">PubMed</a>' : '';
    return '<li>' + line + link + apa + '</li>';
}

function formatCollapsibleSourcesHtml(title, itemHtmlList) {
    if (!itemHtmlList || !itemHtmlList.length) return '';
    const visible = itemHtmlList.slice(0, AI_SOURCES_VISIBLE_COUNT);
    const hidden = itemHtmlList.slice(AI_SOURCES_VISIBLE_COUNT);
    let html = '<div class="ai-references-block ai-references-collapsible"><strong>' + escapeHtml(title) + '</strong><ul>';
    html += visible.join('');
    html += '</ul>';
    if (hidden.length) {
        const expandLabel = 'Show ' + hidden.length + ' more source' + (hidden.length === 1 ? '' : 's');
        html += '<details class="ai-sources-details">';
        html += '<summary class="ai-sources-summary" aria-label="' + escapeHtml(expandLabel) + '" title="' + escapeHtml(expandLabel) + '"><span class="ai-sources-show-more-icon" aria-hidden="true">▾</span></summary>';
        html += '<ul>' + hidden.join('') + '</ul>';
        html += '</details>';
    }
    html += '</div>';
    return html;
}

function extractCitedPmidsFromText(text) {
    const raw = String(text || '');
    const seen = {};
    const ordered = [];
    const patterns = [
        /pubmed\.ncbi\.nlm\.nih\.gov\/(\d+)/gi,
        /\bPMID[:\s#]*(\d+)\b/gi
    ];
    patterns.forEach(function (re) {
        var m;
        re.lastIndex = 0;
        while ((m = re.exec(raw)) !== null) {
            var p = m[1];
            if (p && !seen[p]) {
                seen[p] = true;
                ordered.push(p);
            }
        }
    });
    return ordered;
}

function extractCitedUrlsFromText(text) {
    const raw = String(text || '');
    const seen = {};
    const ordered = [];
    var m;
    const mdRe = /\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g;
    while ((m = mdRe.exec(raw)) !== null) {
        var u = m[2].replace(/[).,;]+$/, '');
        if (u && !seen[u]) {
            seen[u] = true;
            ordered.push(u.toLowerCase());
        }
    }
    const bareRe = /(https?:\/\/[^\s)\]>"']+)/g;
    while ((m = bareRe.exec(raw)) !== null) {
        u = m[1].replace(/[).,;]+$/, '');
        if (u && !seen[u]) {
            seen[u] = true;
            ordered.push(u.toLowerCase());
        }
    }
    return ordered;
}

function filterPubmedRefsForReply(replyText, refs) {
    if (!refs || !refs.length) return [];
    const text = String(replyText || '');
    if (!text.trim()) return [];
    const citedPmids = extractCitedPmidsFromText(text);
    if (citedPmids.length) {
        const byPmid = {};
        refs.forEach(function (r) {
            if (r && r.pmid) byPmid[String(r.pmid)] = r;
        });
        return citedPmids.map(function (p) { return byPmid[p]; }).filter(Boolean);
    }
    const citedUrls = extractCitedUrlsFromText(text);
    if (citedUrls.length) {
        const matched = [];
        const seenP = {};
        refs.forEach(function (r) {
            var url = String(r && r.url || '').replace(/\/$/, '').toLowerCase();
            if (!url) return;
            var hit = citedUrls.some(function (cu) { return url.indexOf(cu) >= 0 || cu.indexOf(url) >= 0; });
            if (hit) {
                var pmid = String(r.pmid || '');
                if (pmid && seenP[pmid]) return;
                if (pmid) seenP[pmid] = true;
                matched.push(r);
            }
        });
        if (matched.length) return matched;
    }
    const lower = text.toLowerCase();
    const titleMatched = [];
    const seenP2 = {};
    refs.forEach(function (r) {
        var title = String(r && r.title || '').trim();
        if (title.length < 12) return;
        if (lower.indexOf(title.slice(0, 48).toLowerCase()) >= 0) {
            var pmid2 = String(r.pmid || '');
            if (pmid2 && seenP2[pmid2]) return;
            if (pmid2) seenP2[pmid2] = true;
            titleMatched.push(r);
        }
    });
    return titleMatched;
}

function formatReferencesHtml(refs) {
    if (!refs || !refs.length) return '';
    const items = refs.map(function (r, i) {
        return formatPubMedReferenceLi(r, i >= AI_SOURCES_VISIBLE_COUNT);
    });
    return formatCollapsibleSourcesHtml('Literature sources', items);
}

function getDirectChildUl(el) {
    if (!el || !el.children) return null;
    for (var i = 0; i < el.children.length; i++) {
        if (el.children[i].tagName === 'UL') return el.children[i];
    }
    return null;
}

function finalizeAiReferenceBlocks(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('.ai-references-block').forEach(function (block) {
        if (block.querySelector('.ai-sources-details')) return;
        const firstUl = getDirectChildUl(block);
        if (!firstUl) return;
        const items = Array.prototype.slice.call(firstUl.children).filter(function (el) {
            return el.tagName === 'LI';
        });
        if (items.length <= AI_SOURCES_VISIBLE_COUNT) return;
        const hidden = items.slice(AI_SOURCES_VISIBLE_COUNT);
        const expandLabel = 'Show ' + hidden.length + ' more source' + (hidden.length === 1 ? '' : 's');
        const details = document.createElement('details');
        details.className = 'ai-sources-details';
        const summary = document.createElement('summary');
        summary.className = 'ai-sources-summary';
        summary.setAttribute('aria-label', expandLabel);
        summary.title = expandLabel;
        summary.innerHTML = '<span class="ai-sources-show-more-icon" aria-hidden="true">▾</span>';
        const ul = document.createElement('ul');
        hidden.forEach(function (li) { ul.appendChild(li); });
        details.appendChild(summary);
        details.appendChild(ul);
        block.appendChild(details);
    });
}

async function submitUserFeedback() {
    const statusEl = document.getElementById('userFeedbackStatus');
    const msgEl = document.getElementById('userFeedbackMessage');
    if (!currentUser) return;
    const message = (msgEl && msgEl.value) ? msgEl.value.trim() : '';
    if (statusEl) statusEl.textContent = '';
    if (message.length < 4) {
        if (statusEl) statusEl.textContent = 'Please enter a longer message.';
        return;
    }
    if (!currentUser.feedback_token) {
        if (statusEl) statusEl.textContent = 'Please log out and log in once to enable feedback, then try again.';
        return;
    }
    try {
        await apiService.submitFeedback({
            username: currentUser.username,
            message,
            source: 'user',
            feedback_token: currentUser.feedback_token,
        });
        if (msgEl) msgEl.value = '';
        if (statusEl) {
            statusEl.textContent = 'Thank you — your feedback was sent.';
            statusEl.style.color = 'var(--success-color, #10b981)';
        }
    } catch (e) {
        if (statusEl) {
            statusEl.style.color = 'var(--error-color, #ef4444)';
            let msg = e.message || 'Could not send feedback.';
            if (
                e.code === 'feedback_token_invalid' ||
                e.code === 'feedback_token_missing' ||
                msg.includes('feedback session') ||
                msg.includes('FEEDBACK_AUTH_SECRET')
            ) {
                msg =
                    'Log out, log in again, then try feedback. ' +
                    'If this keeps happening after every site update, set FEEDBACK_AUTH_SECRET on Render (see PAID_DEPLOYMENT.md).';
            }
            statusEl.textContent = msg;
        }
    }
}

function updatePwaInstallButtonVisibility() {
    const standalone =
        (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
        window.navigator.standalone === true;
    ['userInstallAppBtn'].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) el.style.display = standalone ? 'none' : '';
    });
}

/**
 * Header "Install" — uses browser install prompt when available (Chrome/Edge/Android Chrome),
 * otherwise short instructions (e.g. Safari Share → Add to Home Screen).
 */
function installWellbeingApp() {
    const standalone =
        (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
        window.navigator.standalone === true;
    if (standalone) {
        showToast('You are already using the installed app.', 'info');
        return;
    }
    if (deferredPwaPrompt) {
        deferredPwaPrompt.prompt();
        deferredPwaPrompt.userChoice.then(function () {
            deferredPwaPrompt = null;
        });
        return;
    }
    const ua = navigator.userAgent || '';
    const isIOS =
        /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (isIOS) {
        showToast('Tap Share, then Add to Home Screen (Safari).', 'info');
    } else if (/Android/i.test(ua)) {
        showToast(
            'Chrome: tap ⋮ (menu) → Install app or Add to Home screen. Use Google Chrome, not Samsung Internet or an in-app browser. Pull to refresh if you just updated the app.',
            'info',
            9000
        );
    } else {
        showToast('Use the browser menu: Install app or Add to Home screen (Chrome / Edge).', 'info', 7000);
    }
}

function logout() {
    currentUser = null;
    aiConversationHistory = []; // Clear conversation on logout
    userOnboardingActive = false;
    userOnboardingKickoffStarted = false;
    localStorage.removeItem('currentUser');
    showScreen('loginScreen');
    // Clear forms
    document.getElementById('loginForm').reset();
    document.getElementById('registerForm').reset();
    // Force-clear login fields so browser autofill doesn't leave a previous account
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
function showToast(message, type = 'info', durationMs = 3000) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, durationMs);
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

var REFERENCE_SECTION_HEADING_RE = /(?:^|\n)\s*(?:#{1,3}\s*)?(?:\*{0,2}\s*)?(?:(?:Literature\s+sources(?:\s*\([^)]*\))?)|(?:(?:Supporting\s+)?(?:references|sources|citations)))(?:\*{0,2})?\s*:?\s*(?:\n|$)/i;
var REFERENCE_SECTION_HEADING_HTML_RE = /(<br>\s*)*(?:\*{1,2}\s*)?(?:(?:Literature\s+sources(?:\s*\([^)]*\))?)|(?:(?:Supporting\s+)?(?:references|sources|citations)))(?:\*{1,2})?\s*:?\s*<br>/i;
var REFERENCE_BULLET_LINE_RE = /^\s*(?:[-*•‣▪–—]|\d+[.)])\s+(.+)$/;

function normalizeNewlines(text) {
    return String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

function findReferenceSectionIndex(text) {
    const raw = normalizeNewlines(text);
    const patterns = [
        REFERENCE_SECTION_HEADING_RE,
        /(?:^|\n)\s*(?:\*{0,2}\s*)?Literature\s+sources(?:\s*\([^)]*\))?(?:\*{0,2})?\s*:?\s*(?:\n|$)/i
    ];
    let best = -1;
    patterns.forEach(function (re) {
        const idx = raw.search(re);
        if (idx >= 0 && (best < 0 || idx < best)) best = idx;
    });
    return best;
}

var REFERENCE_STRIP_MARKERS = [
    '**supporting references**',
    'supporting references',
    '**literature sources (this reply)**',
    'literature sources (this reply)',
    '**literature sources**',
    'literature sources'
];

function stripReferenceSectionFromText(text) {
    const raw = normalizeNewlines(text);
    const lower = raw.toLowerCase();
    let cut = -1;
    REFERENCE_STRIP_MARKERS.forEach(function (marker) {
        const idx = lower.indexOf(marker);
        if (idx >= 0 && (cut < 0 || idx < cut)) cut = idx;
    });
    if (cut < 0) {
        const idx = findReferenceSectionIndex(raw);
        if (idx < 0) return raw;
        cut = idx;
    }
    return raw.slice(0, cut).replace(/\s+$/, '');
}

function stripReferenceSectionFromHtml(html) {
    if (!html) return html;
    const lower = html.toLowerCase();
    let cut = -1;
    REFERENCE_STRIP_MARKERS.forEach(function (marker) {
        const idx = lower.indexOf(marker);
        if (idx >= 0 && (cut < 0 || idx < cut)) cut = idx;
    });
    if (cut < 0) {
        const patterns = [
            REFERENCE_SECTION_HEADING_HTML_RE,
            /(<br>\s*)*(?:\*{1,2}\s*)?Literature\s+sources(?:\s*\([^)]*\))?(?:\*{1,2})?\s*:?\s*<br>/i
        ];
        patterns.forEach(function (re) {
            const idx = html.search(re);
            if (idx >= 0 && (cut < 0 || idx < cut)) cut = idx;
        });
    }
    if (cut < 0) return html;
    let start = cut;
    const brBefore = html.lastIndexOf('<br>', cut);
    if (brBefore >= 0) start = brBefore;
    return html.slice(0, start).replace(/(<br>\s*)+$/i, '');
}

function extractTrailingReferenceBulletsFromHtml(html) {
    if (!html) return { html: html, items: [] };
    const parts = html.split('<br>');
    const trailing = [];
    let cutAt = parts.length;
    for (let i = parts.length - 1; i >= 0; i--) {
        const t = parts[i].trim();
        if (!t) continue;
        const isBullet = /^(?:[-*•‣▪–—]|\d+[.)])\s/.test(t);
        const isLink = /^<a\s/i.test(t);
        const isPubmed = /pubmed\.ncbi\.nlm\.nih\.gov/i.test(t);
        if (isBullet || isLink || isPubmed) {
            trailing.unshift(t.replace(/^(?:[-*•‣▪–—]|\d+[.)])\s+/, ''));
            cutAt = i;
        } else {
            break;
        }
    }
    if (trailing.length < 2) return { html: html, items: [] };
    return {
        html: parts.slice(0, cutAt).join('<br>').replace(/(<br>\s*)+$/i, ''),
        items: trailing
    };
}

function parseReferenceBulletLine(line) {
    const trimmed = (line || '').trim();
    if (!trimmed) return null;
    const marked = trimmed.match(REFERENCE_BULLET_LINE_RE);
    return marked ? marked[1].trim() : trimmed;
}

function splitSupportingReferencesSection(text) {
    const raw = normalizeNewlines(text);
    let body = raw;
    let bullets = [];

    const headingMatch = raw.match(REFERENCE_SECTION_HEADING_RE);
    if (headingMatch) {
        const idx = raw.search(REFERENCE_SECTION_HEADING_RE);
        body = raw.slice(0, idx).replace(/\s+$/, '');
        const afterHeading = raw.slice(idx + headingMatch[0].length);
        afterHeading.split('\n').forEach(function (line) {
            const item = parseReferenceBulletLine(line);
            if (item) bullets.push(item);
        });
    }

    if (!bullets.length) {
        const fallback = extractTrailingReferenceBullets(body);
        body = fallback.body;
        bullets = fallback.bullets;
    }

    return { body: body, bullets: bullets };
}

function extractTrailingReferenceBullets(body) {
    const lines = normalizeNewlines(body).split('\n');
    const trailing = [];
    let cutAt = lines.length;
    for (let i = lines.length - 1; i >= 0; i--) {
        const item = parseReferenceBulletLine(lines[i]);
        if (!item) {
            if (!lines[i].trim()) {
                continue;
            }
            break;
        }
        trailing.unshift(item);
        cutAt = i;
    }
    if (trailing.length < 2) {
        return { body: body, bullets: [] };
    }
    const kept = lines.slice(0, cutAt).join('\n').replace(/\s+$/, '');
    return { body: kept, bullets: trailing };
}

function extractReferencesSectionFromHtml(html) {
    if (!html) return { html: html, items: [] };
    const match = html.match(REFERENCE_SECTION_HEADING_HTML_RE);
    if (!match) return { html: html, items: [] };
    const idx = html.search(REFERENCE_SECTION_HEADING_HTML_RE);
    const before = html.slice(0, idx).replace(/(<br>\s*)+$/i, '');
    let after = html.slice(idx + match[0].length);
    const items = [];
    after.split('<br>').forEach(function (part) {
        const t = part.trim();
        if (!t) return;
        const cleaned = t.replace(/^(?:[-*•‣▪–—]|\d+[.)])\s+/, '');
        if (cleaned) items.push(cleaned);
    });
    return { html: before, items: items };
}

function formatReferenceListItemHtml(item) {
    if (/<[a-z][\s>]/i.test(item)) {
        return '<li>' + item + '</li>';
    }
    return '<li>' + linkifyEscapedAssistantText(escapeHtml(item)) + '</li>';
}

function linkifyEscapedAssistantText(s) {
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
    return parts.map(function (chunk) {
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
}

function formatSupportingReferencesBlockHtml(bullets) {
    if (!bullets || !bullets.length) return '';
    const items = bullets.map(formatReferenceListItemHtml);
    return formatCollapsibleSourcesHtml('Sources', items);
}

function formatBodyHtml(text) {
    if (text == null || text === '') return '';
    let s = escapeHtml(text);
    s = linkifyEscapedAssistantText(s);
    return s.replace(/\n/g, '<br>');
}

/**
 * Turn assistant text into safe HTML (nutrition plan etc.). Chat uses formatAssistantReplyHtml.
 */
function formatAssistantMessageHtml(text) {
    if (text == null || text === '') return '';
    const split = splitSupportingReferencesSection(normalizeNewlines(text));
    return formatBodyHtml(split.body);
}

function formatAssistantReplyHtml(content, references) {
    const normalized = normalizeNewlines(content);
    const pubmedRefs = Array.isArray(references) ? references : [];

    const split = splitSupportingReferencesSection(normalized);
    let refItems = split.bullets;

    let bodyText = stripReferenceSectionFromText(normalized);
    let bodyHtml = formatBodyHtml(bodyText);
    bodyHtml = stripReferenceSectionFromHtml(bodyHtml);

    if (!refItems.length) {
        const fromHtml = extractReferencesSectionFromHtml(formatBodyHtml(normalized));
        refItems = fromHtml.items;
    }
    if (!refItems.length) {
        const trailing = extractTrailingReferenceBulletsFromHtml(bodyHtml);
        bodyHtml = trailing.html;
        refItems = trailing.items;
    }

    let html = bodyHtml;
    const citedPubmedRefs = filterPubmedRefsForReply(normalized, pubmedRefs);
    if (citedPubmedRefs.length) {
        html += formatReferencesHtml(citedPubmedRefs);
    } else if (refItems.length) {
        html += formatSupportingReferencesBlockHtml(refItems);
    }
    return html;
}

