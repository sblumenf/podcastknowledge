import React from 'react'
import { 
  HiCog, 
  HiViewGrid, 
  HiCheck, 
  HiViewList,
  HiMenu,
  HiMicrophone,
  HiSparkles,
  HiNewspaper,
  HiChip,
  HiAcademicCap,
  HiEmojiHappy,
  HiBriefcase,
  HiUser
} from 'react-icons/hi'

// Custom icon wrapper components as shown in the spec
export const SettingsIcon = (props) => <HiCog {...props} />
export const AppsIcon = (props) => <HiViewGrid {...props} />
export const CheckIcon = (props) => <HiCheck {...props} />
export const GridIcon = (props) => <HiViewGrid {...props} />
export const ListIcon = (props) => <HiViewList {...props} />
export const MenuIcon = (props) => <HiMenu {...props} />
export const UserIcon = (props) => <HiUser {...props} />

// Podcast category icons
export const PodcastIcon = (props) => <HiMicrophone {...props} />
export const SparklesIcon = (props) => <HiSparkles {...props} />
export const NewspaperIcon = (props) => <HiNewspaper {...props} />
export const ChipIcon = (props) => <HiChip {...props} />
export const AcademicCapIcon = (props) => <HiAcademicCap {...props} />
export const EmojiHappyIcon = (props) => <HiEmojiHappy {...props} />
export const BriefcaseIcon = (props) => <HiBriefcase {...props} />