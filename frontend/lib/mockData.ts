export interface SkillNodeData {
  [key: string]: unknown;
  id: string;
  name: string;
  category: 'core' | 'advanced' | 'gap';
  mastery: number; // 0 - 100
  status: 'mastered' | 'developing' | 'weak';
  evidenceCount: number;
  recentActivity: string;
  prerequisites: string[];
  recommendation: string;
}

export interface PlatformConnection {
  id: string;
  name: 'LeetCode' | 'GitHub' | 'HackerRank';
  icon: string;
  connected: boolean;
  username: string | null;
  lastSynced: string | null;
  evidenceCount: number;
  syncing?: boolean;
}

export interface LearningStep {
  id: string;
  title: string;
  category: string;
  status: 'completed' | 'in_progress' | 'recommended' | 'locked';
  mastery: number;
  why: string;
}

export interface CoachMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
  actions?: { label: string; action: string }[];
}

export const MOCK_SKILLS: SkillNodeData[] = [
  {
    id: 'arrays',
    name: 'Arrays & Hashing',
    category: 'core',
    mastery: 92,
    status: 'mastered',
    evidenceCount: 142,
    recentActivity: 'Solved Two Sum & Group Anagrams on LeetCode',
    prerequisites: [],
    recommendation: 'Solid foundation. Keep reviewing edge cases in sliding window problems.',
  },
  {
    id: 'strings',
    name: 'String Manipulation',
    category: 'core',
    mastery: 84,
    status: 'mastered',
    evidenceCount: 98,
    recentActivity: 'Pushed regex parser module on GitHub',
    prerequisites: ['arrays'],
    recommendation: 'Good parsing logic. Try dynamic programming string alignment.',
  },
  {
    id: 'hashing',
    name: 'Hash Tables & Maps',
    category: 'core',
    mastery: 78,
    status: 'developing',
    evidenceCount: 76,
    recentActivity: 'Completed Hash Map domain badge on HackerRank',
    prerequisites: ['arrays'],
    recommendation: 'Strong lookup time awareness. Practice custom hash collision handling.',
  },
  {
    id: 'recursion',
    name: 'Recursion & Backtracking',
    category: 'gap',
    mastery: 51,
    status: 'weak',
    evidenceCount: 34,
    recentActivity: 'Failed call-stack depth limit in N-Queens solver',
    prerequisites: ['arrays'],
    recommendation: 'Critical Gap: Focus on base-case bounds and call-stack trace visualization.',
  },
  {
    id: 'trees',
    name: 'Trees & DFS/BFS',
    category: 'gap',
    mastery: 41,
    status: 'weak',
    evidenceCount: 22,
    recentActivity: 'Attempted Binary Tree Inorder Traversal',
    prerequisites: ['recursion'],
    recommendation: 'Prerequisite Gap: Build confidence in tree recursion before tree dynamic programming.',
  },
  {
    id: 'graphs',
    name: 'Graph Algorithms',
    category: 'gap',
    mastery: 35,
    status: 'weak',
    evidenceCount: 15,
    recentActivity: 'Reviewed Dijkstra shortest path concept',
    prerequisites: ['trees', 'hashing'],
    recommendation: 'Target Goal: Master BFS/DFS traversal patterns before shortest-path optimizers.',
  },
];

export const MOCK_PLATFORMS: PlatformConnection[] = [
  {
    id: 'leetcode',
    name: 'LeetCode',
    icon: 'code-2',
    connected: true,
    username: 'dev_learner_99',
    lastSynced: '10 mins ago',
    evidenceCount: 284,
  },
  {
    id: 'github',
    name: 'GitHub',
    icon: 'git-branch',
    connected: true,
    username: 'mohit-dev',
    lastSynced: '2 hours ago',
    evidenceCount: 112,
  },
  {
    id: 'hackerrank',
    name: 'HackerRank',
    icon: 'terminal',
    connected: false,
    username: null,
    lastSynced: null,
    evidenceCount: 0,
  },
];

export const MOCK_LEARNING_PATH: LearningStep[] = [
  {
    id: 'step-1',
    title: 'Arrays & Hash Maps',
    category: 'Foundations',
    status: 'completed',
    mastery: 92,
    why: 'Demonstrated high fluency across 140+ problem submissions.',
  },
  {
    id: 'step-2',
    title: 'String Parsing & Two Pointers',
    category: 'Foundations',
    status: 'completed',
    mastery: 84,
    why: 'Strong pattern recognition in linear time space tradeoffs.',
  },
  {
    id: 'step-3',
    title: 'Recursion & Backtracking',
    category: 'Identified Skill Gap',
    status: 'in_progress',
    mastery: 51,
    why: 'Your recent solutions show stronger iterative reasoning than recursive traversal.',
  },
  {
    id: 'step-4',
    title: 'Binary Tree Traversal (DFS/BFS)',
    category: 'Next Skill Cluster',
    status: 'recommended',
    mastery: 41,
    why: 'Directly unblocked once recursive call-stack mental model is reinforced.',
  },
  {
    id: 'step-5',
    title: 'Graph Cycle Detection & Shortest Paths',
    category: 'Target Goal',
    status: 'locked',
    mastery: 35,
    why: 'Requires tree DFS fluency and hash map memoization.',
  },
];

export const INITIAL_COACH_MESSAGES: CoachMessage[] = [
  {
    id: 'msg-1',
    sender: 'ai',
    text: "Welcome to Knowledge Mesh AI Coach. I've analyzed your 396 learning evidence items across LeetCode and GitHub.",
    timestamp: '14:20',
  },
  {
    id: 'msg-2',
    sender: 'user',
    text: 'Why am I struggling with tree traversal problems?',
    timestamp: '14:21',
  },
  {
    id: 'msg-3',
    sender: 'ai',
    text: 'Your recent evidence shows strong iterative loop logic (92% mastery in Arrays), but your recursive call-stack depth control is at 51%. Recursion is a prerequisite gap for Binary Trees.',
    timestamp: '14:21',
    actions: [
      { label: 'View Skill Evidence', action: 'evidence' },
      { label: 'Practice Recursion', action: 'practice' },
      { label: 'Open Code Lab', action: 'codelab' },
    ],
  },
];

export const MOCK_CODE_LAB_PROBLEM = {
  id: 'tree-dfs-1',
  title: 'Binary Tree Inorder Traversal',
  difficulty: 'Medium',
  description: `Given the root of a binary tree, return the inorder traversal of its nodes' values.
  
Follow up: Recursive solution is trivial, could you do it iteratively?`,
  initialCode: `// Knowledge Mesh Code Lab - Practice Environment
// Topic: Recursion & Binary Tree Traversal

function inorderTraversal(root) {
    const result = [];
    
    function traverse(node) {
        if (!node) return;
        traverse(node.left);
        result.push(node.val);
        traverse(node.right);
    }
    
    traverse(root);
    return result;
}`,
  tests: [
    { id: 1, input: 'root = [1,null,2,3]', expected: '[1,3,2]' },
    { id: 2, input: 'root = []', expected: '[]' },
    { id: 3, input: 'root = [1]', expected: '[1]' },
  ],
};
