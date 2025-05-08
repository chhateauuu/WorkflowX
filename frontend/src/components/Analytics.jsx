import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  FaSync, 
  FaUser, 
  FaEnvelope, 
  FaCalendarAlt, 
  FaBuilding, 
  FaTags, 
  FaTimes, 
  FaExternalLinkAlt,
  FaInfoCircle,
  FaCheckCircle
} from "react-icons/fa";

const Analytics = () => {
  const [hubspotData, setHubspotData] = useState({ top: [], bottom: [] });
  const [emailsData, setEmailsData] = useState("");
  const [loadingHubspot, setLoadingHubspot] = useState(false);
  const [loadingEmails, setLoadingEmails] = useState(false);
  const [activeTab, setActiveTab] = useState("hubspot");
  const [parsedEmails, setParsedEmails] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [modalContent, setModalContent] = useState(null);
  const [refreshing, setRefreshing] = useState({ hubspot: false, emails: false });
  const [lastRefreshed, setLastRefreshed] = useState({ hubspot: null, emails: null });

  const fetchHubspotData = async () => {
    setLoadingHubspot(true);
    setRefreshing({...refreshing, hubspot: true});
    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: "retrieve hubspot contacts" }),
      });
      
      const data = await response.json();
      if (data.reply) {
        // Parse the text response to extract the contact data
        const topMatches = data.reply.match(/📋 \*\*Top 5 Newest Contacts:\*\*\n((?:👤 .*\n?)*)/);
        const bottomMatches = data.reply.match(/📁 \*\*Bottom 5 Oldest Contacts:\*\*\n((?:👤 .*\n?)*)/);
        
        const parseContacts = (text) => {
          if (!text) return [];
          return text.split('\n')
            .filter(line => line.trim().startsWith('👤'))
            .map(line => {
              const match = line.match(/👤 (.*) (.*) - (.*)/);
              if (match) {
                return {
                  firstname: match[1],
                  lastname: match[2],
                  email: match[3]
                };
              }
              return null;
            })
            .filter(contact => contact !== null);
        };
        
        const topContacts = topMatches ? parseContacts(topMatches[1]) : [];
        const bottomContacts = bottomMatches ? parseContacts(bottomMatches[1]) : [];
        
        setHubspotData({
          top: topContacts,
          bottom: bottomContacts
        });
        
        setLastRefreshed({...lastRefreshed, hubspot: new Date()});
      }
    } catch (error) {
      console.error("Error fetching HubSpot data:", error);
    } finally {
      setLoadingHubspot(false);
      setRefreshing({...refreshing, hubspot: false});
    }
  };

  const fetchEmailsData = async () => {
    setLoadingEmails(true);
    setRefreshing({...refreshing, emails: true});
    try {
      // Add a timestamp to ensure we're getting fresh data each time
      const timestamp = new Date().getTime();
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ 
          message: `get my latest emails timestamp=${timestamp}`,
          dialog_context: { force_refresh: true }
        }),
      });
      
      const data = await response.json();
      if (data.reply) {
        setEmailsData(data.reply);
        
        // Improved regex pattern to better handle multiline content
        const emailRegex = /Email #\d+\s*\nSubject:\s*(.*?)\s*\nFrom:\s*(.*?)\s*\nDate:\s*(.*?)\s*\nSummary:\s*(.*?)\s*\n-{5,}/gs;
        const emails = [];
        let match;
        
        while ((match = emailRegex.exec(data.reply)) !== null) {
          if (match.length >= 5) {
            emails.push({
              subject: match[1].trim(),
              from: match[2].trim(),
              date: match[3].trim(),
              summary: match[4].trim()
            });
          }
        }
        
        // If no emails were parsed but we have a reply, try a fallback method
        if (emails.length === 0 && data.reply.includes("Email #")) {
          console.log("Using fallback email parsing method");
          const emailBlocks = data.reply.split("Email #").filter(block => block.trim().length > 0);
          
          for (const block of emailBlocks) {
            const subjectMatch = block.match(/Subject:\s*(.*?)\s*\n/);
            const fromMatch = block.match(/From:\s*(.*?)\s*\n/);
            const dateMatch = block.match(/Date:\s*(.*?)\s*\n/);
            const summaryMatch = block.match(/Summary:\s*(.*?)(?:\n-{5,}|\n\n|$)/s);
            
            if (subjectMatch && fromMatch && dateMatch && summaryMatch) {
              emails.push({
                subject: subjectMatch[1].trim(),
                from: fromMatch[1].trim(),
                date: dateMatch[1].trim(),
                summary: summaryMatch[1].trim()
              });
            }
          }
        }
        
        console.log(`Parsed ${emails.length} emails from response`);
        setParsedEmails(emails);
        setLastRefreshed({...lastRefreshed, emails: new Date()});
      }
    } catch (error) {
      console.error("Error fetching email data:", error);
    } finally {
      setLoadingEmails(false);
      setRefreshing({...refreshing, emails: false});
    }
  };

  useEffect(() => {
    fetchHubspotData();
    fetchEmailsData();
  }, []);

  const refreshData = (type) => {
    if (type === "hubspot") {
      fetchHubspotData();
    } else if (type === "emails") {
      fetchEmailsData();
    }
  };

  const openContactDetails = (contact) => {
    setModalContent({
      type: 'contact',
      data: contact
    });
    setShowModal(true);
  };

  const openEmailDetails = (email) => {
    setModalContent({
      type: 'email',
      data: email
    });
    setShowModal(true);
  };

  const formatDateTime = (date) => {
    if (!date) return "Never";
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric',
      hour12: true,
      month: 'short',
      day: 'numeric'
    }).format(date);
  };

  return (
    <div className="analytics-container">
      <div className="analytics-header">
        <div className="analytics-title">
          <h1>Analytics Dashboard</h1>
          <p className="analytics-subtitle">View and analyze your HubSpot leads and Gmail emails</p>
        </div>
      </div>
      
      <div className="analytics-tabs">
        <button 
          className={`tab-button ${activeTab === "hubspot" ? "active" : ""}`}
          onClick={() => setActiveTab("hubspot")}
        >
          <FaUser />
          HubSpot Leads
        </button>
        <button 
          className={`tab-button ${activeTab === "emails" ? "active" : ""}`}
          onClick={() => setActiveTab("emails")}
        >
          <FaEnvelope />
          Gmail
        </button>
      </div>
      
      <div className="analytics-meta">
        <div className="analytics-meta-info">
          <FaInfoCircle />
          {activeTab === "hubspot" 
            ? <span>Viewing HubSpot contact data</span>
            : <span>Viewing Gmail email data</span>
          }
        </div>
        
        <div className="analytics-meta-refresh">
          <span className="last-refreshed">
            Last refreshed: {formatDateTime(lastRefreshed[activeTab])}
          </span>
          <motion.button 
            className="refresh-button"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => refreshData(activeTab)}
            disabled={refreshing[activeTab]}
          >
            <FaSync className={refreshing[activeTab] ? "spin" : ""} />
            {refreshing[activeTab] ? "Refreshing..." : "Refresh Data"}
          </motion.button>
        </div>
      </div>
      
      <div className="analytics-content">
        {activeTab === "hubspot" && (
          <motion.div 
            className="hubspot-data"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            {loadingHubspot ? (
              <div className="loading-container">
                <div className="loading-spinner"></div>
                <p>Loading HubSpot data...</p>
              </div>
            ) : (
              <>
                <div className="data-section">
                  <div className="section-header">
                    <h2>Newest Contacts</h2>
                    <div className="badge">Recent</div>
                  </div>
                  <div className="table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th><FaUser /> First Name</th>
                          <th><FaUser /> Last Name</th>
                          <th><FaEnvelope /> Email</th>
                          <th className="actions-column">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {hubspotData.top.length > 0 ? (
                          hubspotData.top.map((contact, index) => (
                            <tr key={`top-${index}`} className="data-row">
                              <td>{contact.firstname}</td>
                              <td>{contact.lastname}</td>
                              <td>{contact.email}</td>
                              <td>
                                <button 
                                  className="view-details-button"
                                  onClick={() => openContactDetails(contact)}
                                >
                                  <FaExternalLinkAlt /> View Details
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="4" className="no-data">No contacts found</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
                
                <div className="data-section">
                  <div className="section-header">
                    <h2>Oldest Contacts</h2>
                    <div className="badge legacy">Legacy</div>
                  </div>
                  <div className="table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th><FaUser /> First Name</th>
                          <th><FaUser /> Last Name</th>
                          <th><FaEnvelope /> Email</th>
                          <th className="actions-column">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {hubspotData.bottom.length > 0 ? (
                          hubspotData.bottom.map((contact, index) => (
                            <tr key={`bottom-${index}`} className="data-row">
                              <td>{contact.firstname}</td>
                              <td>{contact.lastname}</td>
                              <td>{contact.email}</td>
                              <td>
                                <button 
                                  className="view-details-button"
                                  onClick={() => openContactDetails(contact)}
                                >
                                  <FaExternalLinkAlt /> View Details
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="4" className="no-data">No contacts found</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </motion.div>
        )}
        
        {activeTab === "emails" && (
          <motion.div 
            className="emails-data"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            {loadingEmails ? (
              <div className="loading-container">
                <div className="loading-spinner"></div>
                <p>Loading email data...</p>
              </div>
            ) : (
              <div className="data-section">
                <div className="section-header">
                  <h2>Recent Emails</h2>
                  <div className="badge">Inbox</div>
                </div>
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th><FaTags /> Subject</th>
                        <th><FaUser /> From</th>
                        <th><FaCalendarAlt /> Date</th>
                        <th className="actions-column">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {parsedEmails.length > 0 ? (
                        parsedEmails.map((email, index) => (
                          <tr key={`email-${index}`} className="data-row">
                            <td className="email-subject">{email.subject}</td>
                            <td>{email.from}</td>
                            <td>{email.date}</td>
                            <td>
                              <button 
                                className="view-details-button"
                                onClick={() => openEmailDetails(email)}
                              >
                                <FaExternalLinkAlt /> View Details
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="4" className="no-data">No emails found</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </div>
      
      {/* Details Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            className="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="modal-container"
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 20, opacity: 0 }}
              transition={{ type: "spring", damping: 15 }}
            >
              <div className="modal-header">
                <h3>
                  {modalContent?.type === 'contact' ? (
                    <>
                      <FaUser /> Contact Details
                    </>
                  ) : (
                    <>
                      <FaEnvelope /> Email Details
                    </>
                  )}
                </h3>
                <button className="modal-close" onClick={() => setShowModal(false)}>
                  <FaTimes />
                </button>
              </div>
              
              <div className="modal-content">
                {modalContent?.type === 'contact' && (
                  <div className="contact-details">
                    <div className="contact-avatar">
                      {modalContent.data.firstname.charAt(0)}{modalContent.data.lastname.charAt(0)}
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">First Name:</span>
                      <span className="detail-value">{modalContent.data.firstname}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Last Name:</span>
                      <span className="detail-value">{modalContent.data.lastname}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Email:</span>
                      <span className="detail-value email-value">{modalContent.data.email}</span>
                    </div>
                    <div className="detail-actions">
                      <button className="detail-action-button primary">
                        <FaEnvelope /> Send Email
                      </button>
                      <button className="detail-action-button">
                        <FaUser /> View Full Profile
                      </button>
                    </div>
                  </div>
                )}
                
                {modalContent?.type === 'email' && (
                  <div className="email-details">
                    <div className="detail-row">
                      <span className="detail-label">Subject:</span>
                      <span className="detail-value">{modalContent.data.subject}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">From:</span>
                      <span className="detail-value">{modalContent.data.from}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Date:</span>
                      <span className="detail-value">{modalContent.data.date}</span>
                    </div>
                    <div className="detail-row full">
                      <span className="detail-label">Summary:</span>
                      <div className="summary-box">
                        {modalContent.data.summary}
                      </div>
                    </div>
                    <div className="detail-actions">
                      <button className="detail-action-button primary">
                        <FaEnvelope /> Reply
                      </button>
                      <button className="detail-action-button">
                        <FaExternalLinkAlt /> Open in Gmail
                      </button>
                    </div>
                  </div>
                )}
              </div>
              
              <div className="modal-footer">
                <button className="modal-button" onClick={() => setShowModal(false)}>Close</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      
    </div>
  );
};

export default Analytics; 