import Image from 'next/image';

type WorkersAILogoProps = {
  variant?: 'horizontal' | 'compact' | 'stacked' | 'mark' | 'reversed' | 'compact-reversed';
  width?: number;
  className?: string;
  priority?: boolean;
};

const logo = {
  horizontal: { src: '/brand/workersai-logo-horizontal.svg', w: 1150, h: 320 },
  compact: { src: '/brand/workersai-logo-horizontal-compact.svg', w: 1040, h: 250 },
  'compact-reversed': { src: '/brand/workersai-logo-horizontal-compact-reversed.svg', w: 1040, h: 250 },
  stacked: { src: '/brand/workersai-logo-stacked.svg', w: 820, h: 670 },
  mark: { src: '/brand/workersai-mark.svg', w: 440, h: 370 },
  reversed: { src: '/brand/workersai-logo-horizontal-reversed.svg', w: 1150, h: 320 },
} as const;

export function WorkersAILogo({
  variant = 'compact',
  width = 200,
  className,
  priority = false,
}: WorkersAILogoProps) {
  const asset = logo[variant];
  return (
    <Image
      src={asset.src}
      width={width}
      height={Math.round((width * asset.h) / asset.w)}
      alt="WorkersAI"
      priority={priority}
      className={className}
    />
  );
}
