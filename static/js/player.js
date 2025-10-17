// player.js
const player = {
  hp: 100,
  damage: 15,
  baseDamage: 10, // ✅ NEW
  energy: 0,
  isBlocking: false,
  preparingBlock: false,
  isBoosted: false // ✅ NEW
};


function updatePlayerBar() {
  const heroBar = document.getElementById('hero-bar');
  const heroText = document.getElementById('hero-hp');
  heroBar.style.width = player.hp + '%';
  heroText.textContent = player.hp;
  updatePlayerEnergyBar(); // ✅ Add this line
}


function updatePlayerEnergyBar() {
  const energyBar = document.getElementById('player-energy');
  energyBar.style.width = player.energy + '%';

  const blockBtn = document.getElementById('block-btn');
  blockBtn.style.display = 'inline-block'; // ✅ Always show it

  if (player.energy >= 100 && !player.isBlocking && !player.preparingBlock && !isPlayerTurn) {
    energyBar.classList.add('full');
    blockBtn.disabled = false;
    blockBtn.classList.remove('disabled');
  } else {
    energyBar.classList.remove('full');
    blockBtn.disabled = true;
    blockBtn.classList.add('disabled'); // ✅ visually dim
  }
}



function activateBlock() {
  if (player.energy < 100 || player.isBlocking || player.preparingBlock) return;

  player.preparingBlock = true;
  setMessageWithTypewriter('🧠 Loading block challenge... (Listen and type mode)');
  
  // Get a random question for the block challenge
  setBlockChallengeWord();
}

// ✅ NEW: Set block challenge word from question
async function setBlockChallengeWord() {
  const boss = getQueryParam("boss") || 1;
  
  try {
    const response = await fetch(`/get_block_question?level=${boss}`);
    const data = await response.json();
    
    if (data.error) {
      setMessageWithTypewriter('❌ Failed to load block challenge.');
      player.preparingBlock = false;
      return;
    }
    
    // Store the question and answer
    blockChallengeQuestion = data.question;
    blockChallengeAnswer = data.answer; // This is now in the user's lesson language
    
    console.log('Block Challenge Data:', {
      question: blockChallengeQuestion,
      answer: blockChallengeAnswer,
      language: language
    });
    
    // Set the target word to the question
    target = blockChallengeQuestion;
    
    // Update UI for block challenge - always use listen and type mode
    document.getElementById('target').textContent = blockChallengeQuestion;
    setMessageWithTypewriter('🛡️ Type the word above to activate Block! (20% damage reduction)');
    // Remove the answer hint from the output
    document.getElementById('output').textContent = '(waiting...)';
    
    // Show the type box for block challenge
    document.getElementById('word-instruction').style.display = 'none';
    document.querySelector('.recognized').style.display = 'none';
    document.getElementById('type-box').style.display = 'block';
    
    // ✅ Show replay button for block challenges
    const replayBtn = document.getElementById('replay-btn');
    if (replayBtn) {
      replayBtn.style.display = 'inline-block';
    }
    
    // Set mode to type for block challenge
    mode = 'type';
    
    // Auto-play TTS for block challenge question
    playGoogleTTS(blockChallengeQuestion, getLanguageCode(language));
    
    // Focus on the input field and show expected answer
    document.getElementById('typed-input').value = '';
    document.getElementById('typed-input').placeholder = 'Type your answer...';
    document.getElementById('typed-input').focus();
    
  } catch (error) {
    console.error('Error loading block challenge:', error);
    setMessageWithTypewriter('❌ Failed to load block challenge.');
    player.preparingBlock = false;
  }
}


function updateBlockButtonState() {
  const blockBtn = document.getElementById('block-btn');

  if (player.energy >= 100 && !player.isBlocking && !player.preparingBlock && !isPlayerTurn) {
    blockBtn.disabled = false;
    blockBtn.classList.remove('disabled');
    blockBtn.style.opacity = '1';
    blockBtn.style.pointerEvents = 'auto';
    blockBtn.style.display = 'inline-block'; // Show the button
  } else {
    blockBtn.disabled = true;
    blockBtn.classList.add('disabled');
    blockBtn.style.opacity = '0.5';
    blockBtn.style.pointerEvents = 'none';
    // Don't hide the button, just disable it
  }
}

// ✅ NEW: Function to hide shield animations
function hideShieldAnimations() {
  const shieldBarrier = document.getElementById('shield-barrier');
  const shieldBreak = document.getElementById('shield-break');
  
  if (shieldBarrier) {
    shieldBarrier.style.display = 'none';
  }
  if (shieldBreak) {
    shieldBreak.style.display = 'none';
  }
}

// ✅ NEW: Function to show shield barrier
function showShieldBarrier() {
  const shieldBarrier = document.getElementById('shield-barrier');
  if (shieldBarrier) {
    shieldBarrier.style.display = 'block';
  }
}
