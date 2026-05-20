const fs = require('fs');
const path = require('path');

// load conf
const configPath = path.join(__dirname, 'config.json');
let fileStatus;

try {
    fileStatus = JSON.parse(fs.readFileSync(configPath, 'utf8'));
} catch (err) {
    console.error('wtf did you do i cant read conf file :C :', err);
    process.exit(1); // exit if cant read
}

let skippedFiles = []; // skipped files

// enabled = copy files
function copyFileIfEnabled(fileName, source, destination) {
    if (fileStatus[fileName] === 'enabled') {
        const destinationPath = path.join(destination, fileName);
        fs.copyFile(source, destinationPath, (err) => {
            if (err) {
                console.error(`i cant copy :<  ${fileName}:`, err);
            } else {
                console.log(`${fileName} copied successfully to ${destinationPath}!`);
            }
        });
    } else {
        console.log(`${fileName} is set as disabled, ... go enable it if you want it. where? in config ofc! :3.`);
        skippedFiles.push(fileName);
    }
}

// file paths
const filesToCopy = [
    {
        fileName: 'intro.resource',
        source: path.join(__dirname, 'MODS', 'intro.resource'),
        destination: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\SMASH LEGENDS\\Smash_Legends_Data\\Mod'
    },
    {
        fileName: 'sharedassets0.assets',
        source: path.join(__dirname, 'MODS', 'sharedassets0.assets'),
        destination: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\SMASH LEGENDS\\Smash_Legends_Data'
    }
];

// enabled = copy files
filesToCopy.forEach(file => copyFileIfEnabled(file.fileName, file.source, file.destination));

// log skipped after copy
process.on('exit', () => {
    if (skippedFiles.length > 0) {
        console.log('\nThe following files were not copied:');
        skippedFiles.forEach(fileName => console.log(`- ${fileName}`));
    }
    //feel free to modify if youre an modder! script by rylex 💜
});
