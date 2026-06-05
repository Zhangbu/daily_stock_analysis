import type React from 'react';
import { useParams } from 'react-router-dom';
import ProfileStrategyPage from './ProfileStrategyPage';

const PROFILE_CONFIG: Record<string, { title: string; subtitle: string }> = {
  mag7: {
    title: 'Mag7 Strategy Lab',
    subtitle: 'US Big Tech',
  },
  nasdaq100: {
    title: 'Nasdaq-100 Strategy Lab',
    subtitle: 'Nasdaq Constituents',
  },
};

const StrategyLabPage: React.FC = () => {
  const { profileName = 'mag7' } = useParams<{ profileName: string }>();
  const config = PROFILE_CONFIG[profileName] || { title: 'Strategy Lab', subtitle: profileName };

  return (
    <ProfileStrategyPage
      profileName={profileName}
      heroTitle={config.title}
      heroSubtitle={config.subtitle}
    />
  );
};

export default StrategyLabPage;
