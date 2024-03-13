module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.ts?$': 'ts-jest'
  },
  transformIgnorePatterns: ['<rootDir>/node_modules/'],
  setupFilesAfterEnv: ['<rootDir>/jest-setup.js'],
  collectCoverageFrom: ['**/react/**/*.{ts,tsx}'],
  reporters: [
    'default',
    [
      'jest-junit',
      { outputDirectory: 'test-results', outputName: 'results.xml' }
    ]
  ]
};
