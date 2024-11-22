import type { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { address } = req.query

  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method Not Allowed' })
  }

  if (!address || typeof address !== 'string') {
    return res.status(400).json({ message: 'Invalid address parameter' })
  }

  try {
    const response = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/api/address`, {
      params: { address }
    })
    return res.status(200).json(response.data)
  } catch (error) {
    console.error('Error fetching address data:', error)
    return res.status(500).json({ message: 'Error fetching address data' })
  }
}
