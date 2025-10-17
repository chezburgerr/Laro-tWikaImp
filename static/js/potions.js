function loadPotions() {
  fetch('/get_potions')
    .then(res => res.json())
    .then(data => {
      const container = document.getElementById("potions-container");
      container.innerHTML = "";

      if (data.length === 0) {
        container.innerHTML = "<p>No potions available.</p>";
        return;
      }

      data.forEach(potion => {
        const div = document.createElement("div");
        div.className = "potion-circle";

        // If no more quantity, apply disabled look
        if (potion.quantity <= 0) {
          div.classList.add("potion-disabled");
        } else {
          div.onclick = () => usePotion(potion.id);
        }

        div.innerHTML = `
          <div class="potion-icon">
            <img src="https://uktdymsgfgodbwesdvsj.supabase.co/storage/v1/object/public/shopitems/${potion.filename}"
                 alt="Potion">
            <span class="potion-qty">${potion.quantity}</span>
          </div>
        `;

        container.appendChild(div);
      });
    });
}



function usePotion(itemId) {
  fetch('/use-potion/' + itemId, {
    method: 'POST'
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      applyPotionEffect(data.effect);
      loadPotions();
    }
  });
}

function applyPotionEffect(effect) {
  if (!effect || !effect.type) return;

  switch (effect.type) {
    case 'hp':
      const healAmount = Math.floor(100 * (effect.value / 100));
      player.hp += healAmount;
      if (player.hp > 100) player.hp = 100;
      showFloatingHeal('hero-bar', healAmount);
      updatePlayerBar();
      break;

 case 'energy':
  player.energy += effect.value;
  if (player.energy > 100) player.energy = 100;
  updatePlayerEnergyBar();
  showFloatingEnergy('player-energy', effect.value); // 💧 floating MP
  setMessageWithTypewriter(`🧪 Energy potion used! +${effect.value} energy.`);
  playMPEnergySound(); // 🔊 Play MP heal sound
  break;


case 'damageBoost':
  if (!player.isBoosted) {
    player.isBoosted = true;
    player.damage = Math.floor(player.baseDamage * 1.3);
    playPowerupSound(); // 🔊 Play powerup sound
    setMessageWithTypewriter('💥 Damage Boost activated for 10 seconds!');

    setTimeout(() => {
      player.damage = player.baseDamage;
      player.isBoosted = false;

      setMessageWithTypewriter('⚠️ Damage Boost has worn off.');
    }, 10000);
  }
  break;



    case 'timeSlow':
      // Example effect: enemy attack delay increase
      enemy.attackDelay = 5000; // 5 sec
      setTimeout(() => {
        enemy.attackDelay = 3000;
      }, 5000);
      break;
  }
}


// Load on page start
document.addEventListener("DOMContentLoaded", () => {
  loadPotions();
});