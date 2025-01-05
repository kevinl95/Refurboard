const video = document.getElementById('video');
const serverIp = new URLSearchParams(window.location.search).get('server');
const serverUrl = new URL(`http://${serverIp}`);
console.log(serverUrl)
if (navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(function (stream) {
            video.srcObject = stream;
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');

            setInterval(() => {
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                const imageData = canvas.toDataURL('image/png').split(',')[1];
                fetch(`${serverUrl}/stream`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ image: imageData })
                });
            }, 33); // 30fps for better touch screen performance
        })
        .catch(function (error) {
            console.log(error)
            console.log("Something went wrong!");
        });
}