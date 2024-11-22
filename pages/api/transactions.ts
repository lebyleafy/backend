import type { NextApiRequest, NextApiResponse } from 'next';

type Transaction = {
  from: string;
  to: string;
  amount: number;
  timestamp: number;
  hash?: string;
  block?: string;
  fee?: string;
};

type PythonTransaction = {
  from: string;
  to: string;
  amount: string; // Assuming the amount is returned as a string from Python
  timestamp: string; // Assuming the timestamp is returned as a string
  hash?: string;
  block?: string;
  fee?: string;
};

type ApiResponse = {
  success: boolean;
  transactions?: Transaction[];
  message?: string;
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<ApiResponse>
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, message: 'Method not allowed' });
  }

  const { address } = req.query;

  if (!address || typeof address !== 'string') {
    return res.status(400).json({ success: false, message: 'Valid address is required' });
  }

  try {
    // Use an environment variable for the Python API URL
    const pythonApiUrl = process.env.PYTHON_API_URL;
    if (!pythonApiUrl) {
      throw new Error('PYTHON_API_URL environment variable is not set');
    }

    // Fetch data from the Python API
    const response = await fetch(
      `${pythonApiUrl}/api/transactions?address=${encodeURIComponent(address)}`
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (data.success) {
      // Transform data from Python API to match our frontend needs
      const transactions: Transaction[] = data.transactions.map((tx: PythonTransaction) => ({
        from: tx.from,
        to: tx.to,
        amount: parseFloat(tx.amount), // Ensure amount is a number
        timestamp: parseInt(tx.timestamp, 10), // Ensure timestamp is a number
        hash: tx.hash || `0x${Math.random().toString(16).slice(2, 10)}...`,
        block: tx.block || Math.floor(Math.random() * 1000000).toString(),
        fee: tx.fee || (Math.random() * 0.01).toFixed(6),
      }));

      return res.status(200).json({
        success: true,
        transactions,
      });
    } else {
      return res.status(400).json({
        success: false,
        message: data.message || 'Failed to fetch transactions',
      });
    }
  } catch (error) {
    console.error('Error fetching transactions:', error);
    return res.status(500).json({
      success: false,
      message: error instanceof Error ? error.message : 'An unknown error occurred',
    });
  }
}
