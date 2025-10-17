const playerSprite = document.getElementById('player-sprite');

let currentPlayerAnimation = '';
let animationTimeout = null;
let preloadedImages = {};

// Helper to map language to animation suffix
function getLanguageSuffix() {
  switch (language) {
    case 'tagalog': return '1';
    case 'cebuano': return '2';
    case 'waray': return '3';
    default: return '1'; // fallback
  }
}

// Preload all player animations for smooth switching
function preloadPlayerAnimations() {
  const langSuffix = getLanguageSuffix();
  const animations = ['idle', 'attack', 'hurt', 'retreat'];
  
  animations.forEach(state => {
    const path = `/static/sprites/mc${state}${langSuffix}.gif`;
    if (!preloadedImages[path]) {
      const img = new Image();
      img.src = path;
      preloadedImages[path] = img;
    }
  });
}

function setPlayerAnimation(state) {
  if (state === currentPlayerAnimation && state !== 'hurt' && state !== 'attack') return;

  clearTimeout(animationTimeout);
  currentPlayerAnimation = state;

  const langSuffix = getLanguageSuffix();
  let path = '';
  const cacheBuster = `?_=${Date.now()}`;

  switch (state) {
    case 'idle':
      path = `/static/sprites/mcidle${langSuffix}.gif` + cacheBuster;
      break;
    case 'attack':
      path = `/static/sprites/mcattack${langSuffix}.gif` + cacheBuster;
      fireSwordSlash();
      break;
    case 'hurt':
      path = `/static/sprites/mchurt${langSuffix}.gif` + cacheBuster;
      break;
    case 'retreat':
      path = `/static/sprites/mcretreat${langSuffix}.gif` + cacheBuster;
      break;
    default:
      path = `/static/sprites/mcidle${langSuffix}.gif` + cacheBuster;
  }

  // Only update if the path changes
  if (playerSprite.style.backgroundImage !== `url("${path}")`) {
    playerSprite.style.backgroundImage = `url("${path}")`;
  }

  // Remove opacity flicker
  playerSprite.style.opacity = '1';

  // Auto return to idle
  if (state !== 'idle' && state !== 'retreat') {
    animationTimeout = setTimeout(() => {
      setPlayerAnimation('idle');
    }, 1000);
  }
}

// Initialize preloading when language changes
function initializePlayerAnimations() {
  preloadPlayerAnimations();
}

function fireSwordSlash() {
  const slash = document.getElementById('slash-projectile');
  const playerBox = document.getElementById('player-sprite');
  const enemyBox = document.getElementById('enemy-sprite');

  if (!slash || !playerBox || !enemyBox) return;

  // Play player slash sound
  const playerSlashSound = document.getElementById('player-slash-sound');
  if (playerSlashSound) {
    playerSlashSound.currentTime = 0; // Rewind to start
    playerSlashSound.play().catch(e => console.log('Audio play failed:', e));
  }

  // Position the slash at the center of the player (using CSS centering)
  slash.style.display = 'block';
  slash.style.left = '50%';
  slash.style.top = '50%';
  slash.style.transform = 'translate(-50%, -50%)';

  // Force reflow to restart transition
  void slash.offsetWidth;

  // Move slash to enemy position
  const enemyRect = enemyBox.getBoundingClientRect();
  const playerRect = playerBox.getBoundingClientRect();
  const fighterBox = playerBox.closest('.fighter-box');
  const fighterRect = fighterBox.getBoundingClientRect();
  
  // Calculate relative position to enemy
  const relativeEndX = ((enemyRect.left + enemyRect.width / 2) - fighterRect.left) / fighterRect.width * 100;
  
  slash.style.left = `${relativeEndX}%`;

  // Hide slash after it reaches enemy
  setTimeout(() => {
    slash.style.display = 'none';
  }, 600); // Match your CSS transition duration
}
