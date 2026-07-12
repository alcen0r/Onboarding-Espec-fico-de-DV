const socket = io();

socket.on("connect", () => {
    console.log("Conectado ao backend.");
});

socket.on("disconnect", () => {
    console.log("Desconectado do backend.");
});

socket.on("telemetry", (data) => {

    console.log("Telemetria:", data);

    document.getElementById("velocidade").textContent = data.speed;

    document.getElementById("aceleracao").textContent = data.acceleration;

    document.getElementById("motor-status").textContent =
        data.engine ? "ON" : "OFF";

});

document.getElementById("kill-btn").addEventListener("click", () => {

    console.log("Enviando comando KILL...");

    socket.emit("kill");

});
