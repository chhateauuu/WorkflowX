import React, { useState } from "react";
import Navbar from "./components/Navbar";
import ChatWindow from "./components/ChatWindow";
import MessageInput from "./components/MessageInput";
import "./styles.css";

const App = () => {
  const [messages, setMessages] = useState([]);

  const sendMessage = (message) => {
    if (message.trim() !== "") {
      // 1) Add user message to chat
      setMessages([...messages, { text: message, sender: "user" }]);
  
      // 2) Call the backend
      fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: message }),
      })
        .then((res) => res.json())
        .then((data) => {
          // data.reply is the AI's response from the server
          setMessages((prev) => [
            ...prev,
            { text: data.reply, sender: "bot" },
          ]);
        })
        .catch((error) => {
          console.error("Error calling AI endpoint:", error);
          setMessages((prev) => [
            ...prev,
            { text: "Oops, something went wrong with the AI service.", sender: "bot" },
          ]);
        });
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
