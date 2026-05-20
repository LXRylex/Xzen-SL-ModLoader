### **OUTDATED PLEASE USE THE LATEST VERSION**






right click after you opened the folder anywhere in it and click on " open in terminal "

after opening in terminal just write " node xmods.js "

also you have to install nodeJS in order to be able to use it...

here's the link: " https://nodejs.org/dist/v22.6.0/node-v22.6.0-x64.msi " copy and paste it
after installing open the terminal and write " npm install chalk "

THATS ALL UR GOOD TO GO ENJOY :3






this modLoader is compactible with " Yuilix " uploads. if you wish to add more mods you have to do it manually

----------------READ BEFORE MANUAL INSTALLATION-----------------


NOTE THAT THE MODDER OF HIS MOD AND I SHOULD HAVE ALREADY MADE THE MOD TOGETHER IN ORDER FOR IT TO WORK
IF WE EDITED SAME FILES BUT WITHOUT COOPERATING ONLY 1 OF US MODS WILL WORK BECAUSE HE DONT HAVE THE CHANGES I MADE OR I DO.






manually add other mods:

find this code in script given down below.

// file paths
const filesToCopy = [
    {
        fileName: 'intro.resource',
        source: path.join(__dirname, 'MODS', 'intro.resource'),
        destination: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\SMASH LEGENDS\\Smash_Legends_Data\\Mod'
    },
      PASTE ME HERE AND DELETE THIS TEXT
    {
        fileName: 'sharedassets0.assets',
        source: path.join(__dirname, 'MODS', 'sharedassets0.assets'),
        destination: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\SMASH LEGENDS\\Smash_Legends_Data'
    }
];

just copy this given down below

    {
        fileName: 'sharedassets0.assets',
        source: path.join(__dirname, 'MODS', 'sharedassets0.assets'),
        destination: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\SMASH LEGENDS\\Smash_Legends_Data'           <--- this code here with " {} " included.
    }
add this code in the middle of them you see there's " PASTE ME HERE AND DELETE THIS TEXT " ye its self explanatory...
just delete it and put this code above me

dont forget to rename the file name with the one you want to install. 
