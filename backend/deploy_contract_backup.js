const fs = require("fs");
const solc = require("solc");
const Web3 = require("web3").default;

const source = fs.readFileSync("../contracts/managedelection.sol", "utf8");

const input = {
  language: "Solidity",
  sources: {
    "managedelection.sol": {
      content: source,
    },
  },
  settings: {
  evmVersion: "paris",
  outputSelection: {
      "*": {
        "*": ["abi", "evm.bytecode"],
      },
    },
  },
};

const output = JSON.parse(solc.compile(JSON.stringify(input)));

if (output.errors) {
  const errors = output.errors.filter(
    (item) => item.severity === "error"
  );

  if (errors.length) {
    console.error(errors);
    process.exit(1);
  }
}

const compiled =
  output.contracts["managedelection.sol"]["ManageElection"];

const web3 = new Web3("http://127.0.0.1:7545");

async function deploy() {
  const accounts = await web3.eth.getAccounts();
  const admin = accounts[0];

  const contract = new web3.eth.Contract(compiled.abi);

  const deployed = await contract
    .deploy({
      data: "0x" + compiled.evm.bytecode.object,
    })
    .send({
      from: admin,
      gas: 3000000,
    });

  console.log("ADMIN_ACCOUNT =", admin);
  console.log("CONTRACT_ADDRESS =", deployed.options.address);

 fs.writeFileSync("../artifacts/ManageElection.json",
    JSON.stringify(
      {
        abi: compiled.abi,
        bytecode: compiled.evm.bytecode.object,
        contractAddress: deployed.options.address,
      },
      null,
      2
    )
  );

  console.log("Artifact saved to artifacts/ManageElection.json");
}

deploy().catch((error) => {
  console.error("Deployment failed:", error);
  process.exit(1);
});