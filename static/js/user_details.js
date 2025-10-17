document.addEventListener('DOMContentLoaded', () => {
    // Password confirmation validation
    const resetForm = document.querySelector('.password-reset-section form');
    if (resetForm) {
        resetForm.addEventListener('submit', (e) => {
            const newPassword = document.getElementById('new_password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            if (newPassword !== confirmPassword) {
                e.preventDefault();
                alert("Passwords do not match.");
            }
        });
    }

    // Animate avatar thumbnail on hover
    const avatar = document.querySelector('.avatar-thumbnail');
    if (avatar) {
        avatar.addEventListener('mouseenter', () => {
            avatar.style.transform = "scale(1.1)";
        });
        avatar.addEventListener('mouseleave', () => {
            avatar.style.transform = "scale(1)";
        });
    }
});