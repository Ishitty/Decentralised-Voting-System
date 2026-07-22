# 🗳️ Decentralised Blockchain Voting System

A secure blockchain-based online voting platform that combines Ethereum smart contracts, face recognition, and JWT authentication to provide transparent and tamper-resistant digital elections.

## Live Demo

Frontend

https://decentralised-voting-system-rho.vercel.app

Backend API

https://decentralised-voting-system.onrender.com

## Features

- Face Recognition Authentication
- Blockchain-secured Voting
- One Person – One Vote
- JWT-based Admin Authentication
- Voter Registration
- Candidate Management
- Voting Session Scheduling
- Live Election Results
- Fully Deployed Online

## System Architecture

```text
                   User
                    │
                    ▼
          Vercel Frontend
                    │
          REST API Requests
                    │
                    ▼
          Flask Backend (Render)
           │                 │
           │                 │
           ▼                 ▼
 Supabase PostgreSQL    Ethereum Sepolia
                               │
                        Smart Contract
                               │
                          Alchemy RPC
```

## Technology Stack

### Frontend

- HTML5
- CSS3
- JavaScript

### Backend

- Flask
- SQLAlchemy
- Flask-CORS
- JWT

### Database

- Supabase PostgreSQL

### Blockchain

- Solidity
- Web3.py
- Ethereum Sepolia
- Alchemy

### Artificial Intelligence

- OpenCV
- face_recognition
- dlib

### Deployment

- Vercel
- Render

## Project Structure

```text
fyp
│
├── frontend
├── backend
├── contracts
├── artifacts
├── README.md
└── package.json
```

## Security Features

- Face Recognition Authentication
- JWT Protected Admin Dashboard
- Blockchain Vote Recording
- Immutable Vote Storage
- Double Voting Prevention

## Installation

Clone the repository

```bash
git clone https://github.com/Ishitty/Decentralised-Voting-System.git
```

Go to the project

```bash
cd Decentralised-Voting-System/fyp
```

Install dependencies

```bash
pip install -r requirements.txt
npm install
```

Run the backend

```bash
python app.py
```

## Screenshots

Screenshots of the application interface will be added soon.

## Future Scope

- Mobile application
- Multi-factor authentication
- Aadhaar integration
- Email notifications
- Multi-election support
- QR-based voter verification

## Author

Ishit Tyagi

B.Tech Computer Science

## License

This project is released under the MIT License.
