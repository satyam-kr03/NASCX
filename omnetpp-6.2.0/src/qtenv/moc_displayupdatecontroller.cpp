/****************************************************************************
** Meta object code from reading C++ file 'displayupdatecontroller.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "displayupdatecontroller.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'displayupdatecontroller.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 68
#error "This file was generated using the moc from 6.4.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__DisplayUpdateController_t {
    uint offsetsAndSizes[24];
    char stringdata0[40];
    char stringdata1[21];
    char stringdata2[1];
    char stringdata3[6];
    char stringdata4[15];
    char stringdata5[8];
    char stringdata6[5];
    char stringdata7[17];
    char stringdata8[16];
    char stringdata9[8];
    char stringdata10[6];
    char stringdata11[7];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__DisplayUpdateController_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__DisplayUpdateController_t qt_meta_stringdata_omnetpp__qtenv__DisplayUpdateController = {
    {
        QT_MOC_LITERAL(0, 39),  // "omnetpp::qtenv::DisplayUpdate..."
        QT_MOC_LITERAL(40, 20),  // "playbackSpeedChanged"
        QT_MOC_LITERAL(61, 0),  // ""
        QT_MOC_LITERAL(62, 5),  // "speed"
        QT_MOC_LITERAL(68, 14),  // "runModeChanged"
        QT_MOC_LITERAL(83, 7),  // "RunMode"
        QT_MOC_LITERAL(91, 4),  // "mode"
        QT_MOC_LITERAL(96, 16),  // "setPlaybackSpeed"
        QT_MOC_LITERAL(113, 15),  // "RunModeProfile*"
        QT_MOC_LITERAL(129, 7),  // "profile"
        QT_MOC_LITERAL(137, 5),  // "pause"
        QT_MOC_LITERAL(143, 6)   // "resume"
    },
    "omnetpp::qtenv::DisplayUpdateController",
    "playbackSpeedChanged",
    "",
    "speed",
    "runModeChanged",
    "RunMode",
    "mode",
    "setPlaybackSpeed",
    "RunModeProfile*",
    "profile",
    "pause",
    "resume"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__DisplayUpdateController[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       6,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       2,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    1,   50,    2, 0x06,    1 /* Public */,
       4,    1,   53,    2, 0x06,    3 /* Public */,

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       7,    1,   56,    2, 0x0a,    5 /* Public */,
       7,    2,   59,    2, 0x0a,    7 /* Public */,
      10,    0,   64,    2, 0x0a,   10 /* Public */,
      11,    0,   65,    2, 0x0a,   11 /* Public */,

 // signals: parameters
    QMetaType::Void, QMetaType::Double,    3,
    QMetaType::Void, 0x80000000 | 5,    6,

 // slots: parameters
    QMetaType::Void, QMetaType::Double,    3,
    QMetaType::Void, QMetaType::Double, 0x80000000 | 8,    3,    9,
    QMetaType::Void,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::DisplayUpdateController::staticMetaObject = { {
    QMetaObject::SuperData::link<QObject::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__DisplayUpdateController.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__DisplayUpdateController,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__DisplayUpdateController_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<DisplayUpdateController, std::true_type>,
        // method 'playbackSpeedChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<double, std::false_type>,
        // method 'runModeChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<RunMode, std::false_type>,
        // method 'setPlaybackSpeed'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<double, std::false_type>,
        // method 'setPlaybackSpeed'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<double, std::false_type>,
        QtPrivate::TypeAndForceComplete<RunModeProfile *, std::false_type>,
        // method 'pause'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'resume'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::DisplayUpdateController::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<DisplayUpdateController *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->playbackSpeedChanged((*reinterpret_cast< std::add_pointer_t<double>>(_a[1]))); break;
        case 1: _t->runModeChanged((*reinterpret_cast< std::add_pointer_t<RunMode>>(_a[1]))); break;
        case 2: _t->setPlaybackSpeed((*reinterpret_cast< std::add_pointer_t<double>>(_a[1]))); break;
        case 3: _t->setPlaybackSpeed((*reinterpret_cast< std::add_pointer_t<double>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<RunModeProfile*>>(_a[2]))); break;
        case 4: _t->pause(); break;
        case 5: _t->resume(); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (DisplayUpdateController::*)(double );
            if (_t _q_method = &DisplayUpdateController::playbackSpeedChanged; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (DisplayUpdateController::*)(RunMode );
            if (_t _q_method = &DisplayUpdateController::runModeChanged; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 1;
                return;
            }
        }
    }
}

const QMetaObject *omnetpp::qtenv::DisplayUpdateController::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::DisplayUpdateController::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__DisplayUpdateController.stringdata0))
        return static_cast<void*>(this);
    return QObject::qt_metacast(_clname);
}

int omnetpp::qtenv::DisplayUpdateController::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QObject::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 6)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 6;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 6)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 6;
    }
    return _id;
}

// SIGNAL 0
void omnetpp::qtenv::DisplayUpdateController::playbackSpeedChanged(double _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void omnetpp::qtenv::DisplayUpdateController::runModeChanged(RunMode _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 1, _a);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
