// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ManageElection {
    struct Candidate {
        uint id;
        string name;
        uint voteCount;
    }

    mapping(uint => Candidate) public candidates;
    uint public candidateCount;

    // enrollment -> has voted?
    mapping(string => bool) public hasVoted;

    // faceHash (bytes32) -> used for voting?
    mapping(bytes32 => bool) public usedFace;

    // faceHash -> registered?
    mapping(bytes32 => bool) public registeredFace;

    // enrollment -> registered?
    mapping(string => bool) public registeredEnrollment;

    event CandidateAdded(uint id, string name);
    event VoterRegistered(string enrollment, bytes32 faceHash);
    event Voted(string enrollment, bytes32 faceHash, uint candidateId);

    function addCandidate(string memory _name) public {
        candidateCount++;
        candidates[candidateCount] = Candidate(candidateCount, _name, 0);
        emit CandidateAdded(candidateCount, _name);
    }

    function registerVoter(string memory enrollment, bytes32 faceHash) public {
        require(!registeredFace[faceHash], "Face already registered");
        require(!registeredEnrollment[enrollment], "Enrollment already registered");

        registeredFace[faceHash] = true;
        registeredEnrollment[enrollment] = true;

        emit VoterRegistered(enrollment, faceHash);
    }

    function vote(string memory enrollment, bytes32 faceHash, uint candidateId) public {
        require(!hasVoted[enrollment], "You already voted (enrollment)");
        require(!usedFace[faceHash], "Face already used");
        require(candidateId > 0 && candidateId <= candidateCount, "Invalid candidate");

        candidates[candidateId].voteCount++;
        hasVoted[enrollment] = true;
        usedFace[faceHash] = true;

        emit Voted(enrollment, faceHash, candidateId);
    }

    function getCandidate(uint id) public view returns (uint, string memory, uint) {
        Candidate memory c = candidates[id];
        return (c.id, c.name, c.voteCount);
    }
}
