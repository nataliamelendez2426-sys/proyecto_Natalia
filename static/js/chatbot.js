document.addEventListener("DOMContentLoaded", () => {
    const sendBtn = document.getElementById("send-btn");
    const userInput = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");

    sendBtn.addEventListener("click", enviarMensaje);
    userInput.addEventListener("keypress", e => {
        if (e.key === "Enter") enviarMensaje();
    });

    async function enviarMensaje() {
        const mensaje = userInput.value.trim();
        if (!mensaje) return;

        mostrarMensaje("user", mensaje);
        userInput.value = "";

        try {
            const response = await fetch("/cliente/chatbot/mensaje", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mensaje })
            });

            const data = await response.json();
            mostrarMensaje("bot", data.respuesta);

        } catch (error) {
            console.error("Error:", error);
            mostrarMensaje("bot", "❌ Error al conectar con el servidor.");
        }
    }

    function mostrarMensaje(tipo, texto) {
        const msg = document.createElement("div");
        msg.classList.add("message", tipo === "user" ? "user-message" : "bot-message");
        msg.textContent = texto;
        chatBox.appendChild(msg);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});
