/**
 * 0G Serving Broker Bridge — Node.js bridge for Python compute client.
 *
 * Dual-mode:
 *   CLI:    node _broker_bridge.mjs discover | balance | transfer <addr> <amount>
 *   Server: node _broker_bridge.mjs serve [--port 3721]
 */

import { createServer } from 'node:http';
import { ethers } from 'ethers';
import { createZGComputeNetworkBroker } from '@0glabs/0g-serving-broker';
import 'dotenv/config';

// ---------------------------------------------------------------------------
// Broker singleton
// ---------------------------------------------------------------------------

let _broker = null;
let _wallet = null;

async function getBroker() {
  if (_broker) return _broker;

  const privateKey = process.env.PRIVATE_KEY;
  const rpcUrl = process.env.RPC_URL || 'https://evmrpc-testnet.0g.ai';
  if (!privateKey) throw new Error('PRIVATE_KEY not set');

  const provider = new ethers.JsonRpcProvider(rpcUrl);
  _wallet = new ethers.Wallet(privateKey, provider);
  _broker = await createZGComputeNetworkBroker(_wallet);
  return _broker;
}

// ---------------------------------------------------------------------------
// Endpoint normalization
// ---------------------------------------------------------------------------

function normalizeEndpoint(endpoint) {
  // Only strip a literal trailing /chat/completions — don't guess other paths
  if (endpoint.endsWith('/chat/completions')) {
    return endpoint.slice(0, -'/chat/completions'.length);
  }
  return endpoint.replace(/\/+$/, '');
}

// ---------------------------------------------------------------------------
// Core operations
// ---------------------------------------------------------------------------

async function discover() {
  const broker = await getBroker();
  const services = await broker.inference.listService();

  // Tuple: [0]=providerAddress, [1]=serviceType, [2]=url, [6]=model, [10]=teeVerified
  const chatbotServices = services.filter(
    (s) => s[1] === 'chatbot' || s[1] === 'chat'
  );

  const results = [];
  for (const s of chatbotServices) {
    let endpoint = '';
    try {
      const meta = await broker.inference.getServiceMetadata(s[0]);
      endpoint = normalizeEndpoint(meta.endpoint);
    } catch {
      endpoint = s[2] ? normalizeEndpoint(s[2]) : '';
    }
    results.push({
      address: s[0],
      model: s[6],
      teeVerified: Boolean(s[10]),
      endpoint,
    });
  }
  return results;
}

async function metadata(addr) {
  const broker = await getBroker();
  const meta = await broker.inference.getServiceMetadata(addr);
  return {
    endpoint: normalizeEndpoint(meta.endpoint),
    model: meta.model,
  };
}

async function headers(addr) {
  const broker = await getBroker();
  return await broker.inference.getRequestHeaders(addr);
}

async function balance(providerAddr) {
  const broker = await getBroker();

  // Main account — getLedger returns tuple: [0]=addr, [1]=total, [2]=available
  const ledger = await broker.ledger.getLedger();
  const result = {
    main: {
      total: ethers.formatEther(ledger[1]),
      available: ethers.formatEther(ledger[2]),
    },
    sub: null,
  };

  // Provider sub-account if requested
  if (providerAddr) {
    try {
      const [subAccount] = await broker.inference.getAccountWithDetail(providerAddr);
      // subAccount tuple: [0]=user, [1]=provider, [2]=balance, [3]=pendingRefund
      result.sub = {
        provider: subAccount[1],
        balance: ethers.formatEther(subAccount[2]),
      };
    } catch {
      result.sub = null;
    }
  }

  return result;
}

async function acknowledge(addr) {
  const broker = await getBroker();
  await broker.inference.acknowledgeProviderSigner(addr);
  return { ok: true, address: addr };
}

async function processResponse(addr, chatID, usage) {
  const broker = await getBroker();
  await broker.inference.processResponse(addr, chatID, usage);
  return { ok: true };
}

async function transfer(providerAddr, amount) {
  const broker = await getBroker();
  const weiAmount = ethers.parseEther(String(amount));
  await broker.ledger.transferFund(providerAddr, 'inference', weiAmount);
  return { ok: true, provider: providerAddr, amount: String(amount) };
}

// ---------------------------------------------------------------------------
// HTTP Server mode
// ---------------------------------------------------------------------------

function parseQuery(url) {
  const u = new URL(url, 'http://localhost');
  return Object.fromEntries(u.searchParams.entries());
}

function parsePath(url) {
  return new URL(url, 'http://localhost').pathname;
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString());
}

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

async function handleRequest(req, res) {
  const path = parsePath(req.url);
  const query = parseQuery(req.url);

  try {
    if (req.method === 'GET' && path === '/health') {
      json(res, 200, { ok: true });

    } else if (req.method === 'GET' && path === '/discover') {
      json(res, 200, await discover());

    } else if (req.method === 'GET' && path === '/metadata') {
      if (!query.addr) { json(res, 400, { error: 'addr required' }); return; }
      json(res, 200, await metadata(query.addr));

    } else if (req.method === 'GET' && path === '/headers') {
      if (!query.addr) { json(res, 400, { error: 'addr required' }); return; }
      json(res, 200, await headers(query.addr));

    } else if (req.method === 'GET' && path === '/balance') {
      json(res, 200, await balance(query.addr || null));

    } else if (req.method === 'POST' && path === '/process-response') {
      const body = await readBody(req);
      json(res, 200, await processResponse(body.addr, body.chatID, body.usage));

    } else if (req.method === 'POST' && path === '/acknowledge') {
      const body = await readBody(req);
      if (!body.addr) { json(res, 400, { error: 'addr required' }); return; }
      json(res, 200, await acknowledge(body.addr));

    } else if (req.method === 'POST' && path === '/transfer') {
      const body = await readBody(req);
      if (!body.addr || !body.amount) { json(res, 400, { error: 'addr and amount required' }); return; }
      json(res, 200, await transfer(body.addr, body.amount));

    } else {
      json(res, 404, { error: 'not found' });
    }
  } catch (err) {
    console.error(`[broker-bridge] ${path} error:`, err.message);
    json(res, 500, { error: err.message });
  }
}

function startServer(port) {
  const server = createServer(handleRequest);
  server.listen(port, '127.0.0.1', () => {
    console.log(`[broker-bridge] listening on http://127.0.0.1:${port}`);
  });
}

// ---------------------------------------------------------------------------
// CLI mode
// ---------------------------------------------------------------------------

async function cli(args) {
  const command = args[0];

  if (command === 'serve') {
    const portIdx = args.indexOf('--port');
    const port = portIdx !== -1 ? parseInt(args[portIdx + 1], 10) : 3721;
    startServer(port);
    return; // keep running
  }

  let result;
  switch (command) {
    case 'discover':
      result = await discover();
      break;
    case 'balance':
      result = await balance(args[1] || null);
      break;
    case 'metadata':
      if (!args[1]) throw new Error('Usage: metadata <addr>');
      result = await metadata(args[1]);
      break;
    case 'acknowledge':
      if (!args[1]) throw new Error('Usage: acknowledge <addr>');
      result = await acknowledge(args[1]);
      break;
    case 'transfer':
      if (!args[1] || !args[2]) throw new Error('Usage: transfer <addr> <amount>');
      result = await transfer(args[1], args[2]);
      break;
    default:
      console.error('Commands: serve | discover | balance [addr] | metadata <addr> | acknowledge <addr> | transfer <addr> <amount>');
      process.exit(1);
  }

  console.log(JSON.stringify(result, null, 2));
}

cli(process.argv.slice(2)).catch((err) => {
  console.error(JSON.stringify({ error: err.message }));
  process.exit(1);
});
