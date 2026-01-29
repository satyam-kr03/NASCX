/****************************************************************************
** Meta object code from reading C++ file 'modulecanvasviewer.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "modulecanvasviewer.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'modulecanvasviewer.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__ModuleCanvasViewer_t {
    uint offsetsAndSizes[38];
    char stringdata0[35];
    char stringdata1[6];
    char stringdata2[1];
    char stringdata3[13];
    char stringdata4[5];
    char stringdata5[8];
    char stringdata6[12];
    char stringdata7[21];
    char stringdata8[22];
    char stringdata9[8];
    char stringdata10[10];
    char stringdata11[8];
    char stringdata12[12];
    char stringdata13[14];
    char stringdata14[12];
    char stringdata15[6];
    char stringdata16[18];
    char stringdata17[16];
    char stringdata18[15];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__ModuleCanvasViewer_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__ModuleCanvasViewer_t qt_meta_stringdata_omnetpp__qtenv__ModuleCanvasViewer = {
    {
        QT_MOC_LITERAL(0, 34),  // "omnetpp::qtenv::ModuleCanvasV..."
        QT_MOC_LITERAL(35, 5),  // "click"
        QT_MOC_LITERAL(41, 0),  // ""
        QT_MOC_LITERAL(42, 12),  // "QMouseEvent*"
        QT_MOC_LITERAL(55, 4),  // "back"
        QT_MOC_LITERAL(60, 7),  // "forward"
        QT_MOC_LITERAL(68, 11),  // "doubleClick"
        QT_MOC_LITERAL(80, 20),  // "contextMenuRequested"
        QT_MOC_LITERAL(101, 21),  // "std::vector<cObject*>"
        QT_MOC_LITERAL(123, 7),  // "objects"
        QT_MOC_LITERAL(131, 9),  // "globalPos"
        QT_MOC_LITERAL(141, 7),  // "dragged"
        QT_MOC_LITERAL(149, 11),  // "marqueeZoom"
        QT_MOC_LITERAL(161, 13),  // "exportToImage"
        QT_MOC_LITERAL(175, 11),  // "exportToPdf"
        QT_MOC_LITERAL(187, 5),  // "print"
        QT_MOC_LITERAL(193, 17),  // "setLayoutingScene"
        QT_MOC_LITERAL(211, 15),  // "QGraphicsScene*"
        QT_MOC_LITERAL(227, 14)   // "layoutingScene"
    },
    "omnetpp::qtenv::ModuleCanvasViewer",
    "click",
    "",
    "QMouseEvent*",
    "back",
    "forward",
    "doubleClick",
    "contextMenuRequested",
    "std::vector<cObject*>",
    "objects",
    "globalPos",
    "dragged",
    "marqueeZoom",
    "exportToImage",
    "exportToPdf",
    "print",
    "setLayoutingScene",
    "QGraphicsScene*",
    "layoutingScene"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__ModuleCanvasViewer[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
      11,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       7,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    1,   80,    2, 0x06,    1 /* Public */,
       4,    0,   83,    2, 0x06,    3 /* Public */,
       5,    0,   84,    2, 0x06,    4 /* Public */,
       6,    1,   85,    2, 0x06,    5 /* Public */,
       7,    2,   88,    2, 0x06,    7 /* Public */,
      11,    1,   93,    2, 0x06,   10 /* Public */,
      12,    1,   96,    2, 0x06,   12 /* Public */,

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
      13,    0,   99,    2, 0x0a,   14 /* Public */,
      14,    0,  100,    2, 0x0a,   15 /* Public */,
      15,    0,  101,    2, 0x0a,   16 /* Public */,
      16,    1,  102,    2, 0x0a,   17 /* Public */,

 // signals: parameters
    QMetaType::Void, 0x80000000 | 3,    2,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, 0x80000000 | 3,    2,
    QMetaType::Void, 0x80000000 | 8, QMetaType::QPoint,    9,   10,
    QMetaType::Void, QMetaType::QPointF,    2,
    QMetaType::Void, QMetaType::QRectF,    2,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, 0x80000000 | 17,   18,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::ModuleCanvasViewer::staticMetaObject = { {
    QMetaObject::SuperData::link<QGraphicsView::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__ModuleCanvasViewer.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__ModuleCanvasViewer,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__ModuleCanvasViewer_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<ModuleCanvasViewer, std::true_type>,
        // method 'click'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QMouseEvent *, std::false_type>,
        // method 'back'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'forward'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'doubleClick'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QMouseEvent *, std::false_type>,
        // method 'contextMenuRequested'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<const std::vector<cObject*> &, std::false_type>,
        QtPrivate::TypeAndForceComplete<const QPoint &, std::false_type>,
        // method 'dragged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QPointF, std::false_type>,
        // method 'marqueeZoom'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QRectF, std::false_type>,
        // method 'exportToImage'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'exportToPdf'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'print'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'setLayoutingScene'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QGraphicsScene *, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::ModuleCanvasViewer::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<ModuleCanvasViewer *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->click((*reinterpret_cast< std::add_pointer_t<QMouseEvent*>>(_a[1]))); break;
        case 1: _t->back(); break;
        case 2: _t->forward(); break;
        case 3: _t->doubleClick((*reinterpret_cast< std::add_pointer_t<QMouseEvent*>>(_a[1]))); break;
        case 4: _t->contextMenuRequested((*reinterpret_cast< std::add_pointer_t<std::vector<cObject*>>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<QPoint>>(_a[2]))); break;
        case 5: _t->dragged((*reinterpret_cast< std::add_pointer_t<QPointF>>(_a[1]))); break;
        case 6: _t->marqueeZoom((*reinterpret_cast< std::add_pointer_t<QRectF>>(_a[1]))); break;
        case 7: _t->exportToImage(); break;
        case 8: _t->exportToPdf(); break;
        case 9: _t->print(); break;
        case 10: _t->setLayoutingScene((*reinterpret_cast< std::add_pointer_t<QGraphicsScene*>>(_a[1]))); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (ModuleCanvasViewer::*)(QMouseEvent * );
            if (_t _q_method = &ModuleCanvasViewer::click; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (ModuleCanvasViewer::*)();
            if (_t _q_method = &ModuleCanvasViewer::back; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 1;
                return;
            }
        }
        {
            using _t = void (ModuleCanvasViewer::*)();
            if (_t _q_method = &ModuleCanvasViewer::forward; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 2;
                return;
            }
        }
        {
            using _t = void (ModuleCanvasViewer::*)(QMouseEvent * );
            if (_t _q_method = &ModuleCanvasViewer::doubleClick; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 3;
                return;
            }
        }
        {
            using _t = void (ModuleCanvasViewer::*)(const std::vector<cObject*> & , const QPoint & );
            if (_t _q_method = &ModuleCanvasViewer::contextMenuRequested; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 4;
                return;
            }
        }
        {
            using _t = void (ModuleCanvasViewer::*)(QPointF );
            if (_t _q_method = &ModuleCanvasViewer::dragged; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 5;
                return;
            }
        }
        {
            using _t = void (ModuleCanvasViewer::*)(QRectF );
            if (_t _q_method = &ModuleCanvasViewer::marqueeZoom; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 6;
                return;
            }
        }
    }
}

const QMetaObject *omnetpp::qtenv::ModuleCanvasViewer::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::ModuleCanvasViewer::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__ModuleCanvasViewer.stringdata0))
        return static_cast<void*>(this);
    return QGraphicsView::qt_metacast(_clname);
}

int omnetpp::qtenv::ModuleCanvasViewer::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QGraphicsView::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 11)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 11;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 11)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 11;
    }
    return _id;
}

// SIGNAL 0
void omnetpp::qtenv::ModuleCanvasViewer::click(QMouseEvent * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void omnetpp::qtenv::ModuleCanvasViewer::back()
{
    QMetaObject::activate(this, &staticMetaObject, 1, nullptr);
}

// SIGNAL 2
void omnetpp::qtenv::ModuleCanvasViewer::forward()
{
    QMetaObject::activate(this, &staticMetaObject, 2, nullptr);
}

// SIGNAL 3
void omnetpp::qtenv::ModuleCanvasViewer::doubleClick(QMouseEvent * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 3, _a);
}

// SIGNAL 4
void omnetpp::qtenv::ModuleCanvasViewer::contextMenuRequested(const std::vector<cObject*> & _t1, const QPoint & _t2)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t2))) };
    QMetaObject::activate(this, &staticMetaObject, 4, _a);
}

// SIGNAL 5
void omnetpp::qtenv::ModuleCanvasViewer::dragged(QPointF _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 5, _a);
}

// SIGNAL 6
void omnetpp::qtenv::ModuleCanvasViewer::marqueeZoom(QRectF _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 6, _a);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
