import React, { useState } from "react";
import Navbar from "./components/Navbar";
import ChatWindow from "./components/ChatWindow";
import MessageInput from "./components/MessageInput";
import "./styles.css";

const App = () => {
  const [messages, setMessages] = useState([]);

  const sendMessage = (message) => {
    if (message.trim() !== "") {
      setMessages([...messages, { text: message, sender: "user" }]);

      setTimeout(() => {
        setMessages((prev) => [...prev, { text: "🤖 AI is thinking...", sender: "bot" }]);
      }, 1000);
    }
  };

  return (
    <div className="app-container">
      <Navbar />
      <div className="chat-container">
        <ChatWindow messages={messages} />
        <MessageInput onSend={sendMessage} />
      </div>
    </div>
  );
};

export default App;
