// enemy-animation.js

const enemySprite = document.getElementById('enemy-sprite');

let currentEnemyAnimation = '';
let enemyAnimationTimeout = null;
let enemyPreloadedImages = {};

// Preload all enemy animations for smooth switching
function preloadEnemyAnimations() {
  const animations = ['idle', 'attack', 'hurt', 'retreat'];
  
  animations.forEach(state => {
    const path = `/static/sprites/enemy${state}.gif`;
    if (!enemyPreloadedImages[path]) {
      const img = new Image();
      img.src = path;
      enemyPreloadedImages[path] = img;
    }
  });
}

function setEnemyAnimation(state) {
  // Always allow retrigger for attack and hurt by resetting background
  if (state === currentEnemyAnimation && state !== 'hurt' && state !== 'attack') return;

  clearTimeout(enemyAnimationTimeout);
  currentEnemyAnimation = state;

  let path = '';
  const cacheBuster = `?_=${Date.now()}`;
  switch (state) {
    case 'idle':
      path = '/static/sprites/enemyidle.gif' + cacheBuster;
      break;
    case 'attack':
      path = '/static/sprites/enemyattack.gif' + cacheBuster;
      break;
    case 'hurt':
      path = '/static/sprites/enemyhurt.gif' + cacheBuster;
      break;
    case 'retreat':
      path = '/static/sprites/enemyretreat.gif' + cacheBuster;
      break;
    default:
      path = '/static/sprites/enemyidle.gif' + cacheBuster;
  }

  // Only update if the path changes
  if (enemySprite.style.backgroundImage !== `url("${path}")`) {
    enemySprite.style.backgroundImage = `url("${path}")`;
  }

  // Remove opacity flicker
  enemySprite.style.opacity = '1';

  // Auto return to idle after 1 sec (except retreat)
  if (state !== 'idle' && state !== 'retreat') {
    enemyAnimationTimeout = setTimeout(() => {
      setEnemyAnimation('idle');
    }, 1000);
  }
}

// Initialize preloading
function initializeEnemyAnimations() {
  preloadEnemyAnimations();
}

window.addEventListener('load', () => {
  setTimeout(() => {
    initializeEnemyAnimations();
    setEnemyAnimation('idle');
  }, 100);
});


