// --- DOM Element References ---
const qIn = document.getElementById('question');
const ans = document.getElementById('answer');
const btn = document.getElementById('askButton');
const spinner = document.getElementById('spinner');
const icon = document.getElementById('buttonIcon');
const historyContainer = document.getElementById('historyContainer');
const quickActionsContainer = document.getElementById('quickActionsContainer');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const exploreFeaturesSection = document.getElementById('exploreFeaturesSection');
const mainContent = document.getElementById('mainContent');
const buttonTextSpan = document.getElementById('buttonText');

const initialAnswerPlaceholder = '<span class="italic text-gray-500">Your answer will appear here...</span>';
const HISTORY_KEY = 'jerseyAiHistory';
const MAX_HISTORY = 10;

// --- History Functions ---
function loadHistory() {
  historyContainer.innerHTML = '';
  const history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  if (history.length === 0) {
    const noHistoryEl = document.createElement('p');
    noHistoryEl.id = 'noHistory';
    noHistoryEl.className = 'text-sm text-gray-500 italic';
    noHistoryEl.textContent = 'No chat history yet.';
    historyContainer.appendChild(noHistoryEl);
  } else {
      const existingNoHistory = document.getElementById('noHistory');
      if (existingNoHistory) existingNoHistory.remove();
      history.forEach(item => addHistoryEntry(item.question, item.answer, item.timestamp, false));
  }
}

function saveToHistory(question, answer) {
    const timestamp = new Date().toISOString();
    const history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    history.push({ question, answer, timestamp });
    while (history.length > MAX_HISTORY) {
        history.shift();
    }
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    addHistoryEntry(question, answer, timestamp, true);
}

function addHistoryEntry(question, answerHtml, isoTimestamp, isNewEntry) {
    const existingNoHistory = document.getElementById('noHistory');
      if (existingNoHistory) existingNoHistory.remove();

    const entryDiv = document.createElement('div');
    entryDiv.className = 'history-entry text-sm cursor-pointer';
    entryDiv.setAttribute('role', 'button');
    entryDiv.setAttribute('tabindex', '0');

    const timeAgo = formatTimeAgo(isoTimestamp);
    const answerSnippet = answerHtml.replace(/<[^>]*>/g, ' ').substring(0, 60);

    entryDiv.innerHTML = `
        <p class="text-gray-600 mb-0.5 text-xs sm:text-sm">
            <span class="font-medium text-gray-800">You:</span> ${escapeHtml(question)}
        </p>
        <p class="text-gray-600 text-xs sm:text-sm">
            <span class="font-medium text-red-600">AI:</span> ${escapeHtml(answerSnippet)}...
        </p>
        <p class="text-[10px] sm:text-xs text-gray-500 mt-1">${timeAgo}</p>
    `;

    const loadHistoryItem = () => {
        qIn.value = question;
        ans.innerHTML = answerHtml;
        ans.classList.remove('italic', 'text-red-600');
        qIn.focus();
    };

    entryDiv.addEventListener('click', loadHistoryItem);
    entryDiv.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            loadHistoryItem();
        }
    });

    if (isNewEntry) {
        historyContainer.insertBefore(entryDiv, historyContainer.firstChild);
    } else {
        historyContainer.appendChild(entryDiv);
    }
}

/**
 * Clears the chat history from UI and local storage.
 */
function clearHistory() {
    if (confirm('Are you sure you want to clear the chat history?')) {
        try {
            localStorage.removeItem(HISTORY_KEY);
            historyContainer.innerHTML = ''; // Clear UI
            // Re-create and append the 'no history' message
            const noHistoryEl = document.createElement('p');
            noHistoryEl.id = 'noHistory';
            noHistoryEl.className = 'text-sm text-gray-500 italic';
            noHistoryEl.textContent = 'No chat history yet.';
            historyContainer.appendChild(noHistoryEl);
        } catch (error) {
             console.error("Error during history clearing:", error); // Keep error logging
        }
    }
}

// --- Utility Functions ---
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

  function formatTimeAgo(isoTimestamp) {
    const date = new Date(isoTimestamp);
    const now = new Date();
    const secondsPast = (now.getTime() - date.getTime()) / 1000;
    if (secondsPast < 60) return `${Math.round(secondsPast)}s ago`;
    if (secondsPast < 3600) return `${Math.round(secondsPast / 60)}m ago`;
    if (secondsPast <= 86400) return `${Math.round(secondsPast / 3600)}h ago`;
    const dayDiff = Math.round(secondsPast / 86400);
    if (dayDiff === 1) return 'Yesterday';
    if (dayDiff < 7) return `${dayDiff}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// --- Core Functionality ---
async function askQuestion() {
  const questionText = qIn.value.trim();
  if (!questionText) {
    ans.innerHTML = '<span class="italic text-red-600 font-medium">Please type your question above.</span>';
    return;
  }

  btn.disabled = true;
  btn.classList.add('opacity-60', 'cursor-not-allowed');
  spinner.classList.remove('hidden');
  icon.style.opacity='0';
  ans.innerHTML = '<span class="italic text-gray-500">Thinking...</span>';
  ans.classList.add('loading-pulse');
  ans.setAttribute('aria-busy', 'true');
  ans.classList.remove('text-red-600');

  try {
    await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate API call
    // Updated simulated answer to use green text for the question part
    const simulatedAnswerHtml = `<p class="font-semibold text-green-700 mb-2">Simulated Answer for: "${escapeHtml(questionText)}"</p><p>This is a placeholder response demonstrating how the answer area can be populated. In a real application, this would contain the actual information retrieved based on your question about Jersey.</p>`;
    ans.innerHTML = simulatedAnswerHtml;
    ans.classList.remove('italic');
    saveToHistory(questionText, simulatedAnswerHtml);
  } catch(e) {
    console.error("Error asking question:", e);
    ans.innerHTML = `<span class="font-semibold text-red-600">⚠️ Error:</span> <span class="text-gray-700">Could not get an answer. Please try again later.</span>`;
  } finally {
    btn.disabled = false;
    btn.classList.remove('opacity-60', 'cursor-not-allowed');
    spinner.classList.add('hidden');
    icon.style.opacity='1';
    ans.classList.remove('loading-pulse');
    ans.setAttribute('aria-busy', 'false');
    // qIn.value = ''; // Optional: Clear input
  }
}

// --- Event Listeners ---
qIn.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    if (!btn.disabled) btn.click();
  }
});

quickActionsContainer.addEventListener('click', (event) => {
    const button = event.target.closest('.quick-action-btn');
    if (button && button.dataset.question) {
        qIn.value = button.dataset.question;
        qIn.focus();
    }
});

exploreFeaturesSection.addEventListener('click', (event) => {
    const card = event.target.closest('.feature-card-btn');
    if (card && card.dataset.question) {
        qIn.value = card.dataset.question;
        qIn.focus();
    }
});
exploreFeaturesSection.addEventListener('keydown', (event) => {
    const card = event.target.closest('.feature-card-btn');
     if (card && card.dataset.question && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault();
        qIn.value = card.dataset.question;
        qIn.focus();
     }
});

// Ensure the clear history button listener is correctly attached
if (clearHistoryBtn) {
     clearHistoryBtn.addEventListener('click', clearHistory);
} else {
     console.error("Clear History button not found!");
}


// --- Initial Setup ---
document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    ans.innerHTML = initialAnswerPlaceholder;

    // Set initial button text
    if (buttonTextSpan) {
        buttonTextSpan.textContent = "Let's Go!";
    }

    // Re-check attachment just in case
    // The clearHistoryBtn event listener is already attached above,
    // but if it were conditional or complex, this is a good place for a robust check.
    if (clearHistoryBtn && !clearHistoryBtn._eventAttached) { // Using a custom property to track
         clearHistoryBtn.addEventListener('click', clearHistory);
         clearHistoryBtn._eventAttached = true; // Mark as attached
    }
});
