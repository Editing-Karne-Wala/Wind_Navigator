document.addEventListener('DOMContentLoaded', () => {
    let dummyName = "Abhinav";
    let dummyEmail = "abhinav208000@gmail.com";
    let dummyPass = "123456789";

    const loginPage = document.getElementById('loginPage');
    const regPage = document.getElementById('regPage');
    const reglink = document.getElementById('reglink');
    const lLoginBtn = document.getElementById('lLoginBtn');
    const rRegBtn = document.getElementById('rRegBtn');

    reglink.addEventListener('click', () => {
        loginPage.style.display = 'none';
        regPage.style.display = 'flex';
        document.getElementById('curFile').innerText = 'activity_registration.xml';
    });

    rRegBtn.addEventListener('click', () => {
        dummyName = document.getElementById('rName').value;
        dummyEmail = document.getElementById('rEmail').value;
        dummyPass = document.getElementById('rPass').value;
        regPage.style.display = 'none';
        loginPage.style.display = 'flex';
        document.getElementById('curFile').innerText = 'activity_login.xml';
    });

    lLoginBtn.addEventListener('click', async () => {
        const email = document.getElementById('lEmail').value;
        const pass = document.getElementById('lPass').value;
        
        if (email === dummyEmail && pass === dummyPass) {
            reglink.innerText = "Processing...";
            try {
                const response = await fetch(`https://api.genderize.io/?name=${dummyName}`);
                const data = await response.json();
                reglink.innerText = `Login Success - Gender: ${data.gender}`;
            } catch (error) {
                reglink.innerText = "Login Success - Gender: Unknown";
            }
        } else {
            reglink.innerText = "Login Failed";
        }
    });
});
