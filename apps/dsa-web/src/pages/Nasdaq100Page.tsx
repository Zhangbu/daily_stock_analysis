import type React from 'react';
import ProfileStrategyPage from './ProfileStrategyPage';

const Nasdaq100Page: React.FC = () => {
  return (
    <ProfileStrategyPage
      profileName="nasdaq100"
      heroTitle="Nasdaq-100 Strategy Lab"
      heroSubtitle="Nasdaq Constituents"
    />
  );
};

export default Nasdaq100Page;
