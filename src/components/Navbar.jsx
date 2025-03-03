import React, { useState } from "react";
import { FaUserCircle } from "react-icons/fa";

const Navbar = () => {
  const [dropdownOpen, setDropdownOpen] = useState(false);

  return (
    <nav className="navbar">
      <div className="navbar-left">
        <span className="brand">WorkflowX</span>
        <span className="dashboard">Dashboard</span>
      </div>
      <div className="navbar-right">
        <div className="profile-container">
          <FaUserCircle 
            className="profile-icon" 
            onClick={() => setDropdownOpen(!dropdownOpen)}
          />
          {dropdownOpen && (
            <div className="dropdown-menu">
              <p className="dropdown-item">View Profile</p>
              <p className="dropdown-item">Sign Out</p>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
