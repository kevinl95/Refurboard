const video = document.getElementById('video');
const serverIp = new URLSearchParams(window.location.search).get('server');

function startVideo(constraints) {
    navigator.mediaDevices.getUserMedia(constraints)
        .then(function (stream) {
            video.srcObject = stream;
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');

            setInterval(() => {
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                const imageData = canvas.toDataURL('image/png').split(',')[1];
                fetch(`${serverIp}/stream`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ image: imageData })
                });
            }, 33); // 30fps for better touch screen performance
        })
        .catch(function (error) {
            console.log(error);
            console.log("Something went wrong!");
        });
}

const constraints = {
    video: {
        facingMode: { exact: 'environment' }
    }
};

navigator.mediaDevices.getUserMedia(constraints)
    .then(stream => {
        startVideo(constraints);
    })
    .catch(error => {
        console.log('Environment camera not found, trying user camera');
        startVideo({ video: { facingMode: 'user' } });
    });