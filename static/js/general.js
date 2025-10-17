// general.js

// Queue for typewriter effects to prevent overlapping
let typewriterQueue = [];
let isTypewriterRunning = false;

// Typewriter effect function
function typewriterEffect(element, text, speed = 20) {
  return new Promise((resolve) => {
    // Clear any existing content and stop any running typewriter
    element.classList.remove('typewriter');
    element.textContent = '';
    
    // Add typewriter class and start typing
    element.classList.add('typewriter');
    
    let i = 0;
    const timer = setInterval(() => {
      if (i < text.length) {
        element.textContent += text.charAt(i);
        i++;
      } else {
        clearInterval(timer);
        setTimeout(() => {
          element.classList.remove('typewriter');
          resolve();
        }, 1000); // Keep cursor for 1 second after completion
      }
    }, speed);
  });
}

// Helper function to set message with typewriter effect (queued)
async function setMessageWithTypewriter(text, speed = 20) {
  const msgBox = document.getElementById('message-box');
  
  // Add to queue
  typewriterQueue.push({ text, speed, element: msgBox });
  
  // Process queue if not already running
  if (!isTypewriterRunning) {
    processTypewriterQueue();
  }
}

// Process the typewriter queue
async function processTypewriterQueue() {
  if (typewriterQueue.length === 0) {
    isTypewriterRunning = false;
    return;
  }
  
  isTypewriterRunning = true;
  const { text, speed, element } = typewriterQueue.shift();
  
  await typewriterEffect(element, text, speed);
  
  // Process next item in queue
  processTypewriterQueue();
}

let allWords = {};
let targetWords = [];
let currentIndex = 0;
let recognized = '';
let target = '';
let language = 'tagalog';
let isPlayerTurn = true; // 🔁 True during player's attack phase

// ✅ Block challenge variables (accessible from player.js)
let blockChallengeQuestion = null;
let blockChallengeAnswer = null;



function getQueryParam(param) {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(param);
}

async function loadWords() {
  const boss = getQueryParam("boss") || 1;
  const res = await fetch(`/get_words?level=${boss}`);
  const data = await res.json();

  // Get the only key in the returned object (e.g., "waray", "cebuano", etc.)
  const detectedLang = Object.keys(data)[0];
  language = detectedLang; // 🔄 update global language
  allWords = data;
  targetWords = allWords[language];

  currentIndex = 0;
  setWord();

  setPlayerAnimation('idle');
}



function replayTTS() {
  const targetText = document.getElementById("target").textContent;
  const languageCode = getLanguageCode(language);
  
  console.log('🔊 Replay TTS Debug:', {
    targetText: targetText,
    targetTextLength: targetText.length,
    targetTextTrimmed: targetText.trim(),
    language: language,
    languageCode: languageCode
  });
  
  // Clean the text before sending
  const cleanText = targetText.trim();
  if (cleanText) {
    playGoogleTTS(cleanText, languageCode);
  } else {
    console.error('❌ Empty text for TTS');
  }
}

function setWord() {
  isPlayerTurn = true;
  updateBlockButtonState();

  const currentItem = targetWords[currentIndex];
  target = currentItem.word;

  const rawType = currentItem.type?.trim().toLowerCase();
  console.log(`Item #${currentIndex + 1} type:`, rawType);

  if (rawType === 'listen') {
    mode = 'type';
  } else if (rawType === 'speak') {
    mode = 'speak';
  } else {
    mode = 'type';
    console.warn(`Invalid type "${rawType}" — defaulting to type`);
  }

  document.getElementById('target').textContent = target;
  setMessageWithTypewriter(
    mode === 'speak' ? 'Say the word to attack!' : 'Listen and type the word!'
  );
  document.getElementById('output').textContent = '(waiting...)';

  // ✅ Show/Hide "Say this word" line
  document.getElementById('word-instruction').style.display = mode === 'speak' ? 'block' : 'none';

  document.querySelector('.recognized').style.display = (mode === 'speak') ? 'block' : 'none';
  document.getElementById('type-box').style.display = (mode === 'type') ? 'block' : 'none';

  // ✅ Show/Hide replay button for listening questions
  const replayBtn = document.getElementById('replay-btn');
  if (replayBtn) {
    replayBtn.style.display = (mode === 'type') ? 'inline-block' : 'none';
  }

  if (mode === 'type') {
    // Auto-play TTS for listening questions
    playGoogleTTS(target, getLanguageCode(language));
    document.getElementById('typed-input').value = '';
    document.getElementById('typed-input').focus();
  }
}

function nextWord() {
  currentIndex = (currentIndex + 1) % targetWords.length;
  setWord();
}



function getLanguageCode(lang) {
  switch (lang) {
    case 'tagalog': return 'id-ID'; // Use Indonesian for Tagalog (better TTS support)
    case 'waray': return 'id-ID'; // Use Indonesian for Waray (similar phonetics)
    case 'cebuano': return 'id-ID'; // Use Indonesian for Cebuano (similar phonetics)
    default: return 'id-ID'; // Match quiz.html default
  }
}

function checkAnswer() {
  const cleanTarget = target.trim().toLowerCase();
  let userAnswer;
  
  // For block challenges, always use typed input
  if (player.preparingBlock) {
    userAnswer = document.getElementById('typed-input').value.trim().toLowerCase();
  } else {
    // For normal gameplay, use the current mode
    userAnswer = mode === 'speak'
      ? recognized.trim().toLowerCase()
      : document.getElementById('typed-input').value.trim().toLowerCase();
  }

  const msgBox = document.getElementById('message-box');

  // ⛔ Stop flow if game ended
  if (player.hp <= 0 || enemy.hp <= 0) {
    setMessageWithTypewriter('Game Over. Refresh to restart.');
    return;
  }

  // 🛡️ BLOCK CHALLENGE CHECK
  if (player.preparingBlock) {
    // Store the block challenge answer before resetting variables
    const blockAnswerToCheck = blockChallengeAnswer;
    const blockQuestionToCheck = blockChallengeQuestion;
    
    player.preparingBlock = false;
    isPlayerTurn = false; // ✅ Block consumes the turn
    updateBlockButtonState(); // ✅ Update button disabled state

    // Check if the answer matches the block challenge answer
    const cleanBlockAnswer = blockAnswerToCheck.trim().toLowerCase();
    const cleanUserAnswer = userAnswer.trim().toLowerCase();
    
    // More flexible matching - check if user answer contains the expected answer or vice versa
    const isExactMatch = cleanUserAnswer === cleanBlockAnswer;
    const isPartialMatch = cleanUserAnswer.includes(cleanBlockAnswer) || cleanBlockAnswer.includes(cleanUserAnswer);
    const isCloseMatch = Math.abs(cleanUserAnswer.length - cleanBlockAnswer.length) <= 2 && 
                        (cleanUserAnswer.includes(cleanBlockAnswer.substring(0, Math.max(1, cleanBlockAnswer.length - 1))) ||
                         cleanBlockAnswer.includes(cleanUserAnswer.substring(0, Math.max(1, cleanUserAnswer.length - 1))));
    
    console.log('Block Challenge Debug:', {
      userAnswer: cleanUserAnswer,
      expectedAnswer: cleanBlockAnswer,
      originalQuestion: blockQuestionToCheck,
      userAnswerLength: cleanUserAnswer.length,
      expectedAnswerLength: cleanBlockAnswer.length,
      isExactMatch: isExactMatch,
      isPartialMatch: isPartialMatch,
      isCloseMatch: isCloseMatch,
      finalMatch: isExactMatch || isPartialMatch || isCloseMatch,
      userInputValue: document.getElementById('typed-input').value
    });
    
    if (isExactMatch || isPartialMatch || isCloseMatch) {
      player.isBlocking = true;
      player.energy = 0;
      setMessageWithTypewriter('🛡️ Block activated! You will take 20% less damage on the next enemy hit.');
      playShieldUpSound(); // 🔊 Play shield up sound
      // ✅ Show shield barrier
      showShieldBarrier();
    } else {
      player.energy = Math.floor(player.energy / 2);
      setMessageWithTypewriter(`❌ Block failed! You typed "${cleanUserAnswer}" but expected "${cleanBlockAnswer}". Energy reduced by 50%.`);
    }

    // Reset block challenge variables
    blockChallengeQuestion = null;
    blockChallengeAnswer = null;

    // Reset the word display to the current word from the word list
    if (targetWords && targetWords[currentIndex]) {
      const currentItem = targetWords[currentIndex];
      target = currentItem.word;
      document.getElementById('target').textContent = target;
      
      const rawType = currentItem.type?.trim().toLowerCase();
      if (rawType === 'listen') {
        mode = 'type';
        document.getElementById('word-instruction').style.display = 'none';
        document.querySelector('.recognized').style.display = 'none';
        document.getElementById('type-box').style.display = 'block';
        // ✅ Show replay button for listening questions
        const replayBtn = document.getElementById('replay-btn');
        if (replayBtn) {
          replayBtn.style.display = 'inline-block';
        }
      } else {
        mode = 'speak';
        document.getElementById('word-instruction').style.display = 'block';
        document.querySelector('.recognized').style.display = 'block';
        document.getElementById('type-box').style.display = 'none';
        // ✅ Hide replay button for speaking questions
        const replayBtn = document.getElementById('replay-btn');
        if (replayBtn) {
          replayBtn.style.display = 'none';
        }
      }
    }

    updatePlayerBar();
    updateEnemyBar();

    // ✅ Resume flow: enemy attacks
    setTimeout(enemyAttack, 2000);
    return;
  }

  // 🗡️ NORMAL ATTACK CHECK
  if (userAnswer === cleanTarget) {
    enemy.hp -= player.damage;
    setPlayerAnimation('attack');
    showFloatingDamage('enemy-bar', player.damage);
    
    // Play enemy hurt animation when slash reaches enemy (after 600ms)
    setTimeout(() => {
      setEnemyAnimation('hurt');
    }, 600); // Match the slash transition duration

    const energyGained = Math.floor(player.damage * 0.2);
    player.energy += energyGained;
    if (player.energy > 100) player.energy = 100;

    isPlayerTurn = false; // ✅ End player's turn
    updateBlockButtonState();

if (enemy.hp <= 0) {
  enemy.hp = 0;
  setEnemyAnimation('retreat');
  setPlayerAnimation('idle'); // Show victorious player
  setMessageWithTypewriter(`✅ Correct! Enemy is defeated! 🎉`);

  const bossNum = parseInt(getQueryParam("boss")) || 1;
  const completedLevel = bossNum * 100;
  const nextRegularLevel = completedLevel + 1;

  // 👑 Show victory popup with dynamic rewards
  showVictory();

  // Get dynamic rewards from backend
  Promise.all([
    // Get coin reward
    fetch('/api/boss-reward', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        boss: bossNum,
        lesson: language
      })
    }).then(res => res.json()),
    
    // Get EXP reward
    fetch('/api/boss-exp-reward', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        boss: bossNum,
        lesson: language
      })
    }).then(res => res.json())
  ]).then(([coinData, expData]) => {
    console.log("Boss Coins Rewarded:", coinData);
    console.log("Boss EXP Rewarded:", expData);
    
    // Update the reward text with dynamic values
    document.getElementById("reward-text").innerHTML = 
      `You earned 💰 ${coinData.reward} Coins<br>You earned ⭐ ${expData.exp_reward} EXP!`;
    
    // Show level up notification if applicable
    // (Removed: Level up notification now only appears on the level screen)
  }).catch(error => {
    console.error("Error getting boss rewards:", error);
    // Fallback to static rewards if API fails
    const fallbackCoins = Math.floor(200 * Math.pow(1.3, bossNum - 1));
    const fallbackExp = Math.floor(300 * Math.pow(1.3, bossNum - 1));
    document.getElementById("reward-text").innerHTML = 
      `You earned 💰 ${fallbackCoins} Coins<br>You earned ⭐ ${fallbackExp} EXP!`;
  });

  // 🔓 Unlock the completed level
  fetch('/api/complete_level', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      lesson: language,
      level: completedLevel
    })
  });
}


 else {
      setMessageWithTypewriter(`✅ Correct! You hit the enemy! +${energyGained} energy!`);
      updateEnemyBar();
      setTimeout(() => {
        if (!player.preparingBlock) enemyAttack();
      }, 3000);
    }
  } else {
    setMessageWithTypewriter('❌ Incorrect!');
    isPlayerTurn = false; // ✅ Still end turn even if wrong
    updateBlockButtonState();
    setTimeout(() => {
      if (!player.preparingBlock) enemyAttack();
    }, 2000);
  }

  updatePlayerBar();
  updateEnemyBar();
}


function changeLanguage() {
  language = document.getElementById("language-select").value;
  loadWords();
  
  // Reinitialize animations for new language
  if (typeof initializePlayerAnimations === 'function') {
    initializePlayerAnimations();
  }
  if (typeof initializeEnemyAnimations === 'function') {
    initializeEnemyAnimations();
  }
}

const eventSource = new EventSource("/stream");
eventSource.onmessage = function(event) {
  if (event.data.trim()) {
    recognized = event.data;
    document.getElementById("output").textContent = recognized;
  }
};

function updatePlayerPassiveEnergy() {
  if (player.hp <= 0 || enemy.hp <= 0) return;
  player.energy += 20; // gradual gain
  if (player.energy > 100) player.energy = 100;
  updatePlayerEnergyBar();
}

window.onload = function () {
  // ✅ Wait until #player-sprite exists before setting animation
  const checkSpriteReady = setInterval(() => {
    const playerSprite = document.getElementById('player-sprite');
    if (playerSprite) {
      clearInterval(checkSpriteReady);
      
      // Initialize animations for smooth switching
      if (typeof initializePlayerAnimations === 'function') {
        initializePlayerAnimations();
      }
      if (typeof initializeEnemyAnimations === 'function') {
        initializeEnemyAnimations();
      }
      // setPlayerAnimation('idle'); // <-- Remove this line to prevent wrong sprite on first load
    }
  }, 100);

  loadWords();                
  updatePlayerBar();
  updateEnemyBar();
  updateBlockButtonState(); // ✅ Initialize block button state
  hideShieldAnimations(); // ✅ Initialize shield animations as hidden
  
  // Initialize audio settings
  initializeAudio();
  
  setInterval(updateEnergyBar, 1000);
  setInterval(updatePlayerPassiveEnergy, 1000);
};

// ✅ NEW: Initialize audio settings
function initializeAudio() {
  const playerSlashSound = document.getElementById('player-slash-sound');
  const enemySlashSound = document.getElementById('enemy-slash-sound');
  
  if (playerSlashSound) {
    playerSlashSound.volume = 0.7; // Set volume to 70%
  }
  
  if (enemySlashSound) {
    enemySlashSound.volume = 0.7; // Set volume to 70%
  }
}

function showFloatingDamage(targetId, amount) {
  const targetEl = document.getElementById(targetId);
  const damageEl = document.createElement('div');
  damageEl.className = 'damage-text';
  damageEl.textContent = `-${amount}`;

  const rect = targetEl.getBoundingClientRect();
  damageEl.style.left = `${rect.left + rect.width / 2}px`;
  damageEl.style.top = `${rect.top}px`;

  document.body.appendChild(damageEl);

  setTimeout(() => {
    damageEl.remove();
  }, 1000);
}

function showFloatingHeal(targetId, amount) {
  const targetEl = document.getElementById(targetId);
  const healEl = document.createElement('div');
  healEl.className = 'heal-text';
  healEl.textContent = `+${amount}`;

  const rect = targetEl.getBoundingClientRect();
  healEl.style.left = `${rect.left + rect.width / 2}px`;
  healEl.style.top = `${rect.top}px`;

  document.body.appendChild(healEl);

  setTimeout(() => {
    healEl.remove();
  }, 1000);
}

function showFloatingEnergy(targetId, amount) {
  const targetEl = document.getElementById(targetId);
  const energyEl = document.createElement('div');
  energyEl.className = 'heal-text';
  energyEl.style.color = '#00eaff'; // aqua blue for energy
  energyEl.style.zIndex = '9999';   // 🔥 ensure it's on top

  energyEl.textContent = `+${amount} MP`;

  const rect = targetEl.getBoundingClientRect();
  energyEl.style.left = `${rect.left + rect.width / 2}px`;
  energyEl.style.top = `${rect.top - 10}px`; // 💨 slightly above bar

  energyEl.style.position = 'fixed'; // 🧠 fix position relative to screen

  document.body.appendChild(energyEl);

  setTimeout(() => {
    energyEl.remove();
  }, 1000);
}

function goHome() {
  window.location.href = "/levelscreen"; // Change to your home path if different
}

function playGoogleTTS(text, language = "id-ID") {
  console.log('🎤 Google TTS Request:', {
    text: text,
    language: language
  });
  
  fetch("/api/google-tts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text: text,
      language: language
    })
  })
  .then(res => {
    console.log('🎤 Google TTS Response Status:', res.status);
    return res.json();
  })
  .then(data => {
    console.log('🎤 Google TTS Response Data:', data);
    if (data.audio) {
      const audio = new Audio("data:audio/mp3;base64," + data.audio);
      audio.play().catch(err => {
        console.error("Audio Play Error:", err);
      });
    } else {
      console.error("TTS Error:", data.error || "Unknown error");
    }
  })
  .catch(err => {
    console.error("Fetch Error:", err);
  });
}
