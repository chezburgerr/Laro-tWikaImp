const enemy = {
  hp: 100,
  damage: 10,
  energy: 0,
  hasHealed: false,
  boosted: false
};

function updateEnemyBar() {
  const enemyBar = document.getElementById('enemy-bar');
  const energyBar = document.getElementById('enemy-energy');
  const enemyText = document.getElementById('enemy-hp');
  enemyBar.style.width = enemy.hp + '%';
  energyBar.style.width = enemy.energy + '%';
  enemyText.textContent = enemy.hp;
}

function enemyAttack() {
  if (enemy.hp <= 0 || player.hp <= 0) return;

  const resultDiv = document.getElementById('message-box');

  // ✅ Enemy skill activation (only during its turn)
  if (enemy.energy >= 100) {
    if (enemy.hp <= 40 && !enemy.hasHealed) {
      enemy.hp += 30;
      if (enemy.hp > 100) enemy.hp = 100;
      enemy.hasHealed = true;
      enemy.energy = 0;

      setEnemyAnimation('hurt'); // 💉 Play hurt or heal animation
      setMessageWithTypewriter('💀 Enemy used Heal! +30 HP!');
      updateEnemyBar();
      return setTimeout(() => {
        setEnemyAnimation('idle'); // return to idle after heal
        nextWord();
      }, 1000);
    } else {
      enemy.boosted = true;
      setMessageWithTypewriter('⚠️ Enemy is enraged and will deal extra damage!');
      enemy.energy = 0;
    }
  }

  // ✅ Deal damage after skill check
  let dmg = enemy.boosted ? Math.floor(enemy.damage * 1.2) : enemy.damage;
  enemy.boosted = false;

  setEnemyAnimation('attack'); // 🗡️ Animate enemy attack
  
  // Fire enemy slash projectile
  fireEnemySlash();

  // Check if player is blocking
  if (player.isBlocking) {
    dmg = Math.floor(dmg * 0.8); // Reduce by 20%
    player.isBlocking = false;
    setMessageWithTypewriter('🛡️ Your Block reduced the damage by 20%!');
    playShieldImpactSound(); // 🔊 Play shield impact sound
    // Show shield break animation
    const shieldBarrier = document.getElementById('shield-barrier');
    const shieldBreak = document.getElementById('shield-break');
    
    if (shieldBarrier && shieldBreak) {
      // Hide the shield barrier
      shieldBarrier.style.display = 'none';
      
      // Show the break animation
      shieldBreak.style.display = 'block';
      
      // Hide the break animation after it plays (assuming it's a short GIF)
      setTimeout(() => {
        shieldBreak.style.display = 'none';
      }, 2000); // Increased timing for better visibility
    }
  }

  // Apply damage
  player.hp -= dmg;
  if (player.hp < 0) player.hp = 0; // Clamp before showing animation

  showFloatingDamage('hero-bar', dmg);

  // 🎞️ Animate player getting hurt when slash reaches (after 600ms)
  setTimeout(() => {
    if (player.hp > 0) {
      setPlayerAnimation('hurt');
      setTimeout(() => setPlayerAnimation('idle'), 1200); // Return to idle after animation
    } else {
      setPlayerAnimation('retreat'); // Show defeated character
    }
  }, 600); // Match the slash transition duration

  // Message update
  const message = player.hp <= 0
    ? `💀 Enemy strikes back with ${dmg} damage and you fainted!`
    : `💢 Enemy counterattacks with ${dmg} damage!`;
  setMessageWithTypewriter(message);

  // Check for game over
  if (player.hp <= 0) {
    // Calculate reduced rewards (90% reduction)
    const bossNum = parseInt(getQueryParam("boss")) || 1;
    const baseCoins = Math.floor(200 * Math.pow(1.3, bossNum - 1));
    const baseExp = Math.floor(300 * Math.pow(1.3, bossNum - 1));
    const reducedCoins = Math.floor(baseCoins * 0.1); // 10% of original
    const reducedExp = Math.floor(baseExp * 0.1); // 10% of original

    // Show game over screen with reduced rewards
    setTimeout(() => {
      showGameOver(reducedCoins, reducedExp);
    }, 2000);

    // Award reduced rewards
    fetch('/api/boss-reward-reduced', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        boss: bossNum,
        lesson: language,
        reduced_amount: reducedCoins
      })
    }).then(res => res.json())
      .then(data => {
        console.log("Reduced Boss Coins Rewarded:", data);
      });

    fetch('/api/boss-exp-reward-reduced', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        boss: bossNum,
        lesson: language,
        reduced_amount: reducedExp
      })
    }).then(res => res.json())
      .then(data => {
        console.log("Reduced Boss EXP Rewarded:", data);
      });
  }

  // Update bars
  updatePlayerBar();
  updateEnemyBar();

  // Return enemy to idle after attack
  setTimeout(() => {
    if (enemy.hp > 0) setEnemyAnimation('idle');
  }, 1000);

  // Delay next word if block not being prepared
  setTimeout(() => {
    if (!player.preparingBlock) nextWord(); // ⛔ don’t continue until block check done
  }, 1000);
}

function updateEnergyBar() {
  if (enemy.hp <= 0) return;

  enemy.energy += 10;
  if (enemy.energy > 100) enemy.energy = 100;

  const energyBar = document.getElementById('enemy-energy');
  if (enemy.energy >= 100) {
    energyBar.classList.add('full');
  } else {
    energyBar.classList.remove('full');
  }

  updateEnemyBar();
}

// ✅ NEW: Function to fire enemy slash projectile
function fireEnemySlash() {
  const enemySlash = document.getElementById('enemy-slash-projectile');
  const enemyBox = document.getElementById('enemy-sprite');
  const playerBox = document.getElementById('player-sprite');

  if (!enemySlash || !enemyBox || !playerBox) return;

  // Play enemy slash sound
  const enemySlashSound = document.getElementById('enemy-slash-sound');
  if (enemySlashSound) {
    enemySlashSound.currentTime = 0; // Rewind to start
    enemySlashSound.play().catch(e => console.log('Audio play failed:', e));
  }

  // Position the slash at the center of the enemy (using CSS centering)
  enemySlash.style.display = 'block';
  enemySlash.style.left = '50%';
  enemySlash.style.top = '50%';
  enemySlash.style.transform = 'translate(-50%, -50%)';

  // Force reflow to restart transition
  void enemySlash.offsetWidth;

  // Move slash to player position
  const playerRect = playerBox.getBoundingClientRect();
  const enemyRect = enemyBox.getBoundingClientRect();
  const fighterBox = enemyBox.closest('.fighter-box');
  const fighterRect = fighterBox.getBoundingClientRect();
  
  // Calculate relative position to player
  const relativeEndX = ((playerRect.left + playerRect.width / 2) - fighterRect.left) / fighterRect.width * 100;
  
  enemySlash.style.left = `${relativeEndX}%`;

  // Hide slash after it reaches player
  setTimeout(() => {
    enemySlash.style.display = 'none';
  }, 600); // Match your CSS transition duration
}
