const fs = require("fs");
const path = require("path");
const solc = require("solc");
const dotenv = require("dotenv");
const { Web3 } = require("web3");

// Load backend/.env regardless of where the command is run from
const BACKEND_DIR = __dirname;
dotenv.config({ path: path.join(BACKEND_DIR, ".env") });

const RPC_URL = process.env.RPC_URL;
const ADMIN_PRIVATE_KEY = process.env.ADMIN_PRIVATE_KEY;

if (!RPC_URL) {
  throw new Error("RPC_URL is missing from backend/.env");
}

if (!ADMIN_PRIVATE_KEY) {
  throw new Error("ADMIN_PRIVATE_KEY is missing from backend/.env");
}

// Web3 accepts private keys with 0x prefix.
// Add it automatically if your key does not already include it.
const normalizedPrivateKey = ADMIN_PRIVATE_KEY.startsWith("0x")
  ? ADMIN_PRIVATE_KEY
  : `0x${ADMIN_PRIVATE_KEY}`;

const contractPath = path.join(
  BACKEND_DIR,
  "..",
  "contracts",
  "managedelection.sol"
);

const artifactPath = path.join(
  BACKEND_DIR,
  "..",
  "artifacts",
  "ManageElection.json"
);

const source = fs.readFileSync(contractPath, "utf8");

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

console.log("Compiling ManageElection contract...");

const output = JSON.parse(solc.compile(JSON.stringify(input)));

if (output.errors) {
  const warnings = output.errors.filter(
    (item) => item.severity === "warning"
  );

  warnings.forEach((warning) => {
    console.warn(warning.formattedMessage);
  });

  const errors = output.errors.filter(
    (item) => item.severity === "error"
  );

  if (errors.length > 0) {
    errors.forEach((error) => {
      console.error(error.formattedMessage);
    });

    process.exit(1);
  }
}

const compiled =
  output.contracts["managedelection.sol"]["ManageElection"];

if (!compiled?.evm?.bytecode?.object) {
  throw new Error("Compiled contract bytecode was not found.");
}

const web3 = new Web3(RPC_URL);

async function deploy() {
  console.log("Connecting to Sepolia...");

  const isListening = await web3.eth.net.isListening();

  if (!isListening) {
    throw new Error("Unable to connect to the Sepolia RPC.");
  }

  const chainId = await web3.eth.getChainId();

  console.log("Connected. Chain ID:", chainId.toString());

  if (chainId.toString() !== "11155111") {
    throw new Error(
      `Wrong network. Expected Sepolia chain ID 11155111, received ${chainId}.`
    );
  }

  const account = web3.eth.accounts.privateKeyToAccount(
    normalizedPrivateKey
  );

  web3.eth.accounts.wallet.add(account);
  web3.eth.defaultAccount = account.address;

  const balanceWei = await web3.eth.getBalance(account.address);
  const balanceEth = web3.utils.fromWei(balanceWei, "ether");

  console.log("Deployer account:", account.address);
  console.log("Sepolia balance:", `${balanceEth} ETH`);

  if (BigInt(balanceWei) === 0n) {
    throw new Error(
      "The deployer account has no Sepolia ETH for gas."
    );
  }

  const contract = new web3.eth.Contract(compiled.abi);

  const deployment = contract.deploy({
    data: `0x${compiled.evm.bytecode.object}`,
  });

  const estimatedGas = await deployment.estimateGas({
    from: account.address,
  });

  // Add a small buffer over the estimated gas.
  const gasLimit = (BigInt(estimatedGas) * 120n) / 100n;

  console.log("Estimated gas:", estimatedGas.toString());
  console.log("Deploying contract...");

  const deployed = await deployment.send({
    from: account.address,
    gas: gasLimit.toString(),
  });

  const contractAddress = deployed.options.address;

  console.log("");
  console.log("Deployment successful.");
  console.log("ADMIN_ACCOUNT =", account.address);
  console.log("CONTRACT_ADDRESS =", contractAddress);

  fs.mkdirSync(path.dirname(artifactPath), {
    recursive: true,
  });

  fs.writeFileSync(
    artifactPath,
    JSON.stringify(
      {
        abi: compiled.abi,
        bytecode: compiled.evm.bytecode.object,
        contractAddress,
        network: "sepolia",
        chainId: chainId.toString(),
        deployer: account.address,
      },
      null,
      2
    )
  );

  console.log(
    "Artifact saved to artifacts/ManageElection.json"
  );
  console.log("");
  console.log(
    "Now copy the displayed CONTRACT_ADDRESS into backend/.env"
  );
}

deploy().catch((error) => {
  console.error("");
  console.error("Deployment failed:");
  console.error(error.message || error);
  process.exit(1);
});